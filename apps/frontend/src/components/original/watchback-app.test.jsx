import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { getDemoReviewCases } from '@/lib/demo-review-cases';
import { WatchbackApp, buildEvidenceGroups, filterAndSortCases } from './watchback-app';

const cases = getDemoReviewCases();
const fmtTestDate = (iso) => iso.slice(0, 10).replaceAll('-', '.');
const baseProps = {
  initialSelectedId: null,
  initialCases: cases,
  dataSource: 'demo',
  onDataSourceChange: vi.fn(),
  loadState: 'ready',
  loadError: '',
  onRetry: vi.fn(),
  onCreateActivity: vi.fn(),
};

describe('Watchback review UI', () => {
  it('applies the same deterministic filter and sort function to provider results', () => {
    const filters = {
      status: 'open', priority: 'high', changeType: 'all', importance: 'all', staleOnly: false, repo: 'all', sort: 'priority',
    };
    const result = filterAndSortCases(cases, filters, Date.parse('2026-08-26T00:00:00Z'));
    expect(result.length).toBeGreaterThan(0);
    expect(result.every((item) => item.status === 'open' && item.priority === 'high')).toBe(true);
  });

  it('marks demo data on the real review list and keeps systemic change out of filters', () => {
    render(<WatchbackApp {...baseProps} initialView="list" isPreview={false} />);
    expect(screen.getByText('Demo 데이터')).not.toBeNull();
    expect(screen.queryByText('모델 개편에 따른 집단 변동')).toBeNull();
    expect(screen.getAllByRole('button').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Critical').length).toBeGreaterThan(0);
    expect(screen.queryByText('치명적')).toBeNull();
  });

  it('removes dates from list summaries and collapses identical case dates', () => {
    render(<WatchbackApp {...baseProps} initialView="list" isPreview={false} />);

    expect(screen.queryByText(/^\d{4}-\d{2}-\d{2} EPSS/)).toBeNull();
    expect(screen.getAllByText('EPSS 급상승 조건을 충족했습니다.').length).toBeGreaterThan(0);
    const sameDateCase = cases.find((item) => (
      item.opened_at.slice(0, 10) === item.updated_at.slice(0, 10)
    ));
    const matchingCard = screen.getAllByText(sameDateCase.repository.display_name)[0].closest('[role="button"]');
    expect(within(matchingCard).getByText(`생성 ${fmtTestDate(sameDateCase.opened_at)}`)).not.toBeNull();
    expect(within(matchingCard).queryByText(`업데이트 ${fmtTestDate(sameDateCase.updated_at)}`)).toBeNull();
  });

  it('removes the internal D-30 term from dashboard summaries only', () => {
    render(<WatchbackApp {...baseProps} initialView="dashboard" isPreview={false} />);

    expect(screen.getAllByText('EPSS 급상승 조건을 충족했습니다.').length).toBeGreaterThan(0);
    expect(screen.queryByText(/EPSS D-30 급상승 조건/)).toBeNull();
  });

  it('summarizes source-change impact using the reviewed annotations', () => {
    render(<WatchbackApp {...baseProps} initialView="dashboard" isPreview={false} />);

    const sourceImpactCard = screen.getByText('소스 변동 영향 추정').closest('div[style*="cursor"]');
    expect(sourceImpactCard).not.toBeNull();
    expect(screen.getByText('EPSS 모델·소스 변동일과 겹친 재검토 항목')).not.toBeNull();
    expect(within(sourceImpactCard).getByText('지난주 대비 ▲1건')).not.toBeNull();
    expect(screen.queryByText(/시스템성 변동 억제/)).toBeNull();

    fireEvent.click(sourceImpactCard);
    expect(screen.getByText('소스 변동 영향 추정 1건')).not.toBeNull();
    expect(screen.getByText('2026.06.15 · EPSS 모델 v5 전환일')).not.toBeNull();
  });

  it('uses database weekly metrics and arrow icons on every dashboard KPI', () => {
    render(
      <WatchbackApp
        {...baseProps}
        dataSource="db"
        dashboardSummary={{
          reference_at: '2026-08-28T00:00:00Z',
          previous_reference_at: '2026-08-21T00:00:00Z',
          critical_open: { current_count: 4, previous_count: 2, delta: 2 },
          stale_open: { current_count: 1, previous_count: 2, delta: -1 },
          source_impact_open: { current_count: 3, previous_count: 3, delta: 0 },
        }}
        initialView="dashboard"
        isPreview={false}
      />,
    );

    expect(screen.getByText('지난주 대비 ▲2건')).not.toBeNull();
    expect(screen.getByText('지난주 대비 ▼1건')).not.toBeNull();
    expect(screen.getByText('지난주 대비 변화 없음')).not.toBeNull();
    expect(screen.getByText('8/21 ~ 8/28')).not.toBeNull();
    expect(screen.queryByText('기간 비교 미연동')).toBeNull();
  });

  it('shows persistent KEV status before EPSS and stale badges on the dashboard', () => {
    render(<WatchbackApp {...baseProps} initialView="dashboard" isPreview={false} />);

    const kevBadge = screen.getAllByText('KEV')[0];
    const badgeRow = kevBadge.parentElement;
    const labels = [...badgeRow.children].map((element) => element.textContent);

    expect(labels[0]).toBe('KEV');
    expect(labels[1]).toMatch(/^(EPSS 급등|EPSS 상위 5%)$/);
    expect(labels[2]).toMatch(/일째 미처리$/);
  });

  it('renders candidate evidence as a dated timeline on detail', () => {
    render(<WatchbackApp {...baseProps} initialView="detail" initialSelectedId={cases[0].id} isPreview={false} />);
    expect(screen.getByRole('button', { name: '이전 화면으로' })).not.toBeNull();
    expect(screen.getAllByText(/후보 선정/).length).toBeGreaterThan(0);
    expect(screen.getByText('향후 30일 악용 가능성')).not.toBeNull();
  });

  it('hides system case creation from review activities', () => {
    const caseWithOnlySystemCreation = {
      ...cases[0],
      activities: [{
        id: 'activity-case-opened',
        activity_type: 'case_opened',
        actor: null,
        occurred_at: '2026-08-28T00:00:00Z',
        note: null,
        external_links: [],
      }],
    };

    render(
      <WatchbackApp
        {...baseProps}
        initialCases={[caseWithOnlySystemCreation]}
        initialView="detail"
        initialSelectedId={caseWithOnlySystemCreation.id}
        isPreview={false}
      />,
    );

    expect(screen.queryByText('Case 생성')).toBeNull();
    expect(screen.getByText('아직 처리된 사항이 없습니다.')).not.toBeNull();
  });

  it('groups repeated change types while preserving distinct observed evidence', () => {
    const candidates = [
      {
        id: 'candidate-july',
        change_type: 'epss_rise_d30',
        selected_at: '2026-08-27T04:36:17Z',
        reason_summary: 'EPSS가 30일 전 대비 급상승했습니다.',
        deliveries: [{ source_batch_id: 'historical', source_annotations: [] }],
        evidence: [{
          id: 'evidence-july',
          signal: 'epss_score_d30',
          value_type: 'decimal',
          previous_value: '0.07215',
          current_value: '0.38811',
          observed_at: '2026-07-13T00:00:00Z',
          source: 'FIRST EPSS',
          evidence_summary: '7월 EPSS 상승',
        }],
      },
      {
        id: 'candidate-june',
        change_type: 'epss_rise_d30',
        selected_at: '2026-08-27T04:36:17Z',
        reason_summary: 'EPSS가 30일 전 대비 급상승했습니다.',
        deliveries: [{ source_batch_id: 'historical', source_annotations: [] }],
        evidence: [{
          id: 'evidence-june',
          signal: 'epss_score_d30',
          value_type: 'decimal',
          previous_value: '3.2E-4',
          current_value: '0.07215',
          observed_at: '2026-06-13T00:00:00Z',
          source: 'FIRST EPSS',
          evidence_summary: '6월 EPSS 상승',
        }],
      },
      {
        id: 'candidate-exact-redelivery',
        change_type: 'epss_rise_d30',
        selected_at: '2026-08-28T00:00:00Z',
        reason_summary: '동일 근거 재전달',
        deliveries: [{ source_batch_id: 'redelivery', source_annotations: [] }],
        evidence: [{
          id: 'evidence-june-redelivery',
          signal: 'epss_score_d30',
          value_type: 'decimal',
          previous_value: '3.2E-4',
          current_value: '0.07215',
          observed_at: '2026-06-13T00:00:00Z',
          source: 'FIRST EPSS',
          evidence_summary: '동일 근거 재전달',
        }],
      },
    ];

    const groups = buildEvidenceGroups(candidates);

    expect(groups).toHaveLength(1);
    expect(groups[0].changeTypeLabel).toBe('EPSS 급등');
    expect(groups[0].selectedLabel).toBeNull();
    expect(groups[0].evidence.map((item) => item.id)).toEqual([
      'evidence-june',
      'evidence-july',
    ]);
    expect(groups[0].evidence.map((item) => item.candidateId)).toEqual([
      'candidate-june',
      'candidate-july',
    ]);
    expect(groups[0].evidence[0].previousValueLabel).toBe('0.03%');
    expect(groups[0].evidence[1].currentValueLabel).toBe('38.8%');
  });

  it('shows the latest source annotation on the list and both annotations on detail', () => {
    const annotatedCase = cases.find((item) => item.advisory.cve_id === 'CVE-2025-31486');
    const { rerender } = render(
      <WatchbackApp {...baseProps} initialView="list" isPreview={false} />,
    );
    const card = screen.getByText('CVE-2025-31486').closest('[role="button"]');
    expect(within(card).getByText('소스 변동 주의')).not.toBeNull();

    rerender(
      <WatchbackApp
        {...baseProps}
        initialView="detail"
        initialSelectedId={annotatedCase.id}
        isPreview={false}
      />,
    );

    expect(screen.getByText('EPSS 소스 점수 대규모 변동일')).not.toBeNull();
    expect(screen.getByText('EPSS 모델 v5 전환일')).not.toBeNull();
    expect(screen.getByText(/2,677개로 확인/)).not.toBeNull();
    expect(screen.getByText(/모델 변경 영향에 따라/)).not.toBeNull();
    expect(screen.getByText('변동일 2025.11.18')).not.toBeNull();
    expect(screen.getByText('변동일 2026.06.15')).not.toBeNull();
    expect(screen.getAllByRole('link', { name: '출처 보기 ↗' })).toHaveLength(2);
  });

  it('keeps the individual-change label for a case without source annotations', () => {
    const regularCase = cases.find((item) => (
      item.advisory.cve_id !== 'CVE-2025-31486'
    ));
    render(
      <WatchbackApp
        {...baseProps}
        initialView="detail"
        initialSelectedId={regularCase.id}
        isPreview={false}
      />,
    );

    expect(screen.getByText('개별 변화로 확인됨')).not.toBeNull();
    expect(screen.queryByText('소스 변동 주의')).toBeNull();
  });

  it('renders Gold change types naturally without raw sources or duplicate dates', () => {
    const kevCase = cases.find((item) => item.advisory.cve_id === 'CVE-2026-42208');
    render(<WatchbackApp {...baseProps} initialView="detail" initialSelectedId={kevCase.id} isPreview={false} />);

    expect(screen.getByText('KEV 신규 등재')).not.toBeNull();
    expect(screen.queryByText('kev_new')).toBeNull();
    expect(screen.queryByText('cisa_kev')).toBeNull();
    expect(screen.queryByText('first_epss')).toBeNull();
    expect(screen.getAllByText(/2026\.05\.08/)).toHaveLength(1);
    expect(screen.getByText('CISA에서 실제 악용 사례가 확인되었습니다.')).not.toBeNull();
  });

  it('aligns evidence values to the right and expresses percentile as top percentage', () => {
    render(<WatchbackApp {...baseProps} initialView="detail" initialSelectedId={cases[0].id} isPreview={false} />);

    expect(document.querySelector('.watchback-evidence-values')?.style.marginLeft).toBe('auto');
    expect(screen.getAllByText(/^상위 \d+(?:\.\d+)?%$/).length).toBeGreaterThan(0);
    expect(screen.queryByText(/백분위$/)).toBeNull();
  });

  it('places an evidence observation date below the title and values', () => {
    const caseWithDifferentSelectionDate = {
      ...cases[0],
      candidates: cases[0].candidates.map((candidate, index) => (
        index === 0
          ? { ...candidate, selected_at: '2026-08-27T00:30:00Z' }
          : candidate
      )),
    };

    render(
      <WatchbackApp
        {...baseProps}
        initialCases={[caseWithDifferentSelectionDate]}
        initialView="detail"
        initialSelectedId={caseWithDifferentSelectionDate.id}
        isPreview={false}
      />,
    );

    expect(screen.getAllByText(/^관찰일 \d{4}\.\d{2}\.\d{2}$/).length).toBeGreaterThan(0);
  });

  it('separates the EPSS candidate conclusion from its metric evidence', () => {
    const epssCase = cases.find((item) => item.candidates.some((candidate) => (
      candidate.evidence.some((evidence) => evidence.signal === 'epss_percentile_d30')
    )));
    render(<WatchbackApp {...baseProps} initialView="detail" initialSelectedId={epssCase.id} isPreview={false} />);

    expect(screen.getAllByText('EPSS 급등').length).toBeGreaterThan(0);
    expect(screen.getByText('향후 30일 악용 가능성')).not.toBeNull();
    expect(screen.getByText('전체 CVE 내 EPSS 순위')).not.toBeNull();
    expect(screen.getByText(/30일 전보다 \d+(?:\.\d+)?%p 상승했습니다\./)).not.toBeNull();
    expect(screen.getByText('상위 5% 구간에 진입했습니다.')).not.toBeNull();
  });

  it('changes only the selected source and disables preview mutations', () => {
    const onDataSourceChange = vi.fn();
    render(<WatchbackApp {...baseProps} initialView="settings" dataSource="db" onDataSourceChange={onDataSourceChange} isPreview />);
    fireEvent.click(screen.getByRole('button', { name: 'Demo' }));
    expect(onDataSourceChange).toHaveBeenCalledWith('demo');
    expect(screen.getByText('자동조치 정책 DB 연동은 아직 구현되지 않았습니다.')).not.toBeNull();
    expect(screen.getByText('실제 자동조치 정책은 아직 DB와 연동되지 않았습니다.')).not.toBeNull();
    expect(screen.queryByText('현재 모든 위험도 조합은 자동 병합 없이 업데이트 PR 생성까지만 허용합니다.')).toBeNull();
    expect(screen.queryByTitle('UI Preview · 후속 구현')).toBeNull();
  });

  it('shows the synthetic policy matrix only in demo mode', () => {
    render(<WatchbackApp {...baseProps} initialView="settings" isPreview />);
    const policySelects = screen.getAllByTitle('UI Preview · 후속 구현');
    expect(policySelects.every((element) => element.disabled)).toBe(true);
  });

  it('renders retryable and not-found states without demo fallback', () => {
    const { rerender } = render(<WatchbackApp {...baseProps} initialView="list" isPreview={false} loadState="error" loadError="연결 실패" />);
    expect(screen.getByText('연결 실패')).not.toBeNull();
    expect(screen.getByRole('button', { name: '다시 시도' })).not.toBeNull();

    rerender(<WatchbackApp {...baseProps} initialView="detail" initialSelectedId="missing" isPreview={false} loadState="not_found" loadError="없음" />);
    expect(screen.getByText('재검토 Case를 찾을 수 없습니다')).not.toBeNull();
  });

  it('submits the unified activity form for the latest candidate', async () => {
    const onCreateActivity = vi.fn(async () => ({}));
    render(
      <WatchbackApp
        {...baseProps}
        dataSource="db"
        onCreateActivity={onCreateActivity}
        initialView="detail"
        initialSelectedId={cases[0].id}
        isPreview={false}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: '위험 수용' }));
    fireEvent.change(screen.getByLabelText('활동 메모'), { target: { value: '검토 후 위험을 수용합니다.' } });
    fireEvent.change(screen.getByLabelText('외부 링크 유형'), { target: { value: 'issue' } });
    fireEvent.change(screen.getByLabelText('외부 링크 URL'), {
      target: { value: 'https://github.com/novalink/customer-fe/issues/21' },
    });
    fireEvent.click(screen.getByRole('button', { name: '기록하기' }));

    await waitFor(() => expect(onCreateActivity).toHaveBeenCalledWith(cases[0].id, {
      activity_type: 'risk_accepted',
      candidate_id: cases[0].latest_candidate.id,
      note: '검토 후 위험을 수용합니다.',
      external_link: {
        link_type: 'issue',
        url: 'https://github.com/novalink/customer-fe/issues/21',
      },
    }));
  });

  it('validates required notes and matching GitHub link types', () => {
    render(
      <WatchbackApp
        {...baseProps}
        dataSource="db"
        initialView="detail"
        initialSelectedId={cases[0].id}
        isPreview={false}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: '위험 수용' }));
    fireEvent.click(screen.getByRole('button', { name: '기록하기' }));
    expect(screen.getByRole('alert').textContent).toContain('활동 메모');

    fireEvent.change(screen.getByLabelText('활동 메모'), { target: { value: '링크를 확인했습니다.' } });
    fireEvent.change(screen.getByLabelText('외부 링크 유형'), { target: { value: 'issue' } });
    fireEvent.change(screen.getByLabelText('외부 링크 URL'), {
      target: { value: 'https://github.com/novalink/customer-fe/pull/21' },
    });
    fireEvent.click(screen.getByRole('button', { name: '기록하기' }));
    expect(screen.getByRole('alert').textContent).toContain('유형과 일치');
  });

  it('uses the risk acceptance form in demo mode', async () => {
    const onCreateActivity = vi.fn(async () => ({}));
    render(
      <WatchbackApp
        {...baseProps}
        onCreateActivity={onCreateActivity}
        initialView="detail"
        initialSelectedId={cases[0].id}
        isPreview={false}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: '위험 수용' }));
    fireEvent.change(screen.getByLabelText('활동 메모'), { target: { value: 'Demo 위험 수용 사유' } });
    fireEvent.click(screen.getByRole('button', { name: '기록하기' }));
    await waitFor(() => expect(onCreateActivity).toHaveBeenCalledWith(cases[0].id, {
      activity_type: 'risk_accepted',
      candidate_id: cases[0].latest_candidate.id,
      note: 'Demo 위험 수용 사유',
    }));
  });

  it.each([
    ['duplicate_activity', '현재 후보에 같은 활동이 이미 기록되어 있습니다.'],
    ['duplicate_external_link', '이미 연결된 GitHub Issue 또는 PR입니다.'],
    ['organization_scope_violation', '이 조직의 Case에 활동을 기록할 권한이 없습니다.'],
    ['review_case_not_found', '재검토 Case를 찾을 수 없습니다.'],
    ['candidate_not_found', '현재 후보를 이 Case에서 찾을 수 없습니다.'],
    ['backend_unavailable', 'Backend에 연결할 수 없습니다.'],
  ])('shows a specific message for %s', async (code, expectedMessage) => {
    const onCreateActivity = vi.fn(async () => {
      throw Object.assign(new Error('원본 오류'), { code });
    });
    render(
      <WatchbackApp
        {...baseProps}
        dataSource="db"
        onCreateActivity={onCreateActivity}
        initialView="detail"
        initialSelectedId={cases[0].id}
        isPreview={false}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: '위험 수용' }));
    fireEvent.change(screen.getByLabelText('활동 메모'), { target: { value: '검토 메모' } });
    fireEvent.click(screen.getByRole('button', { name: '기록하기' }));
    expect(await screen.findByText(expectedMessage)).not.toBeNull();
  });

  it('blocks repeated submission while a request is pending', async () => {
    let resolveRequest;
    const onCreateActivity = vi.fn(() => new Promise((resolve) => { resolveRequest = resolve; }));
    render(
      <WatchbackApp
        {...baseProps}
        dataSource="db"
        onCreateActivity={onCreateActivity}
        initialView="detail"
        initialSelectedId={cases[0].id}
        isPreview={false}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: '위험 수용' }));
    fireEvent.change(screen.getByLabelText('활동 메모'), { target: { value: '검토 메모' } });
    const submit = screen.getByRole('button', { name: '기록하기' });
    fireEvent.click(submit);
    fireEvent.click(submit);
    expect(onCreateActivity).toHaveBeenCalledTimes(1);
    resolveRequest({});
    await waitFor(() => expect(screen.queryByRole('button', { name: '기록 중…' })).toBeNull());
  });

  it('shows only the primary review actions and marks GitHub creation as unavailable', () => {
    render(
      <WatchbackApp
        {...baseProps}
        dataSource="db"
        initialView="detail"
        initialSelectedId={cases[0].id}
        isPreview={false}
      />,
    );

    expect(screen.getByRole('button', { name: '위험 수용' })).not.toBeNull();
    expect(screen.getByRole('button', { name: '조치하기' })).not.toBeNull();
    expect(screen.queryByRole('button', { name: '메모 추가' })).toBeNull();
    expect(screen.queryByRole('button', { name: '재검토 보류' })).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: '조치하기' }));
    fireEvent.click(screen.getByRole('button', { name: /GitHub Issue 생성/ }));
    expect(screen.getByRole('status').textContent).toContain('GitHub Issue 생성 API는 아직 구현되지 않았습니다.');

    fireEvent.click(screen.getByRole('button', { name: /업데이트 PR 생성/ }));
    expect(screen.getByRole('status').textContent).toContain('업데이트 PR 생성 API는 아직 구현되지 않았습니다.');
  });
});
