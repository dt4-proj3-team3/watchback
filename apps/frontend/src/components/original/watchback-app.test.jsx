import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { getDemoReviewCases } from '@/lib/demo-review-cases';
import { WatchbackApp, buildEvidenceGroups, calculateRereviewScore, filterAndSortCases } from './watchback-app';

const cases = getDemoReviewCases();
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
  it('maps candidate priority to the review index variants', () => {
    expect(calculateRereviewScore({ priority: 'P0' })).toBe(90);
    expect(calculateRereviewScore({ priority: 'P1' })).toBe(65);
    expect(calculateRereviewScore({ priority: 'P2' })).toBe(40);
    expect(calculateRereviewScore({ priority: 'P3' })).toBe(15);
  });

  it('moves the score marker with the selected Figma score variant', () => {
    const highPriorityGroup = cases.find((item) => item.review_priority_candidate.priority === 'P1');
    render(
      <WatchbackApp
        {...baseProps}
        initialView="detail"
        initialSelectedId={highPriorityGroup.id}
        isPreview
      />,
    );

    expect(screen.getByLabelText('재검토 점수 65점')).not.toBeNull();
    const marker = screen.getByTestId('rereview-score-marker');
    expect(marker.style.left).toBe('81px');
    expect(marker.style.top).toBe('11px');
  });

  it('applies the same deterministic filter and sort function to provider results', () => {
    const filters = {
      status: 'open', priority: 'P1', changeType: 'all', importance: 'all', staleOnly: false, repo: 'all', sort: 'priority',
    };
    const result = filterAndSortCases(cases, filters, Date.parse('2026-08-26T00:00:00Z'));
    expect(result.length).toBeGreaterThan(0);
    expect(result.every((item) => (
      item.status === 'open' && item.review_priority_candidate.priority === 'P1'
    ))).toBe(true);
  });

  it('uses the highest unresolved DS candidate priority for vulnerability review', () => {
    const criticalGroups = cases
      .filter((item) => item.review_priority_candidate.priority === 'P0')
      .map((item) => item.cve_id)
      .sort();

    expect(criticalGroups).toEqual([
      'CVE-2025-31125',
      'CVE-2025-55182',
      'CVE-2026-42208',
    ]);
  });

  it('marks demo data on the real review list and keeps systemic change out of filters', () => {
    render(<WatchbackApp {...baseProps} initialView="list" isPreview={false} />);
    expect(screen.getByText('Demo 데이터')).not.toBeNull();
    expect(screen.queryByText('모델 개편에 따른 집단 변동')).toBeNull();
    expect(screen.getAllByRole('button').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Critical').length).toBeGreaterThan(0);
    expect(screen.queryByText('치명적')).toBeNull();
  });

  it('counts repository Critical items by advisory severity instead of DS priority', () => {
    const p0Case = cases.find((item) => item.review_priority_candidate.priority === 'P0');
    const highSeverityP0Case = {
      ...p0Case,
      advisory: { ...p0Case.advisory, severity: 'high' },
    };

    render(
      <WatchbackApp
        {...baseProps}
        initialCases={[highSeverityP0Case]}
        initialView="repos"
        isPreview={false}
      />,
    );

    expect(screen.getByText('열린 항목 1건 · Critical 0건')).not.toBeNull();
    expect(screen.getByText('High')).not.toBeNull();
    expect(screen.queryByText(highSeverityP0Case.repository.full_name)).toBeNull();
    expect(screen.queryByRole('combobox')).toBeNull();
    expect(screen.queryByText(/저장소 목록과 건수는 DB 기준/)).toBeNull();
    expect(screen.queryByText(/P0/)).toBeNull();
  });

  it('adds a selected repository through the repository mock UI', () => {
    render(<WatchbackApp {...baseProps} initialView="repos" isPreview={false} />);

    fireEvent.click(screen.getByRole('button', { name: '+ 저장소 추가' }));
    const dialog = screen.getByRole('dialog', { name: '저장소 추가' });
    expect(within(dialog).queryByLabelText('자동조치 방식')).toBeNull();
    fireEvent.click(within(dialog).getByLabelText('novalink/security-portal'));
    fireEvent.change(within(dialog).getByLabelText('저장소 중요도'), { target: { value: 'medium' } });
    fireEvent.click(within(dialog).getByRole('button', { name: '저장소 추가' }));

    expect(screen.queryByRole('dialog', { name: '저장소 추가' })).toBeNull();
    expect(screen.getByText('novalink/security-portal')).not.toBeNull();
    expect(screen.getAllByText('Medium').length).toBeGreaterThan(0);
  });

  it('shows the organization policy matrix from the repository page', () => {
    render(<WatchbackApp {...baseProps} initialView="repos" isPreview={false} />);

    expect(screen.queryByRole('button', { name: '설정' })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: '자동조치 기본 정책' }));
    const dialog = screen.getByRole('dialog', { name: '자동조치 기본 정책' });
    expect(within(dialog).getAllByRole('combobox')).toHaveLength(12);
    fireEvent.change(within(dialog).getByRole('combobox', { name: 'High 저장소 Critical 취약점 정책' }), { target: { value: 'auto_merge_pr' } });
    fireEvent.click(within(dialog).getByRole('button', { name: '자동조치 기본 정책 닫기' }));
    expect(screen.getAllByText('High/Medium PR 자동 생성 · Critical/Low PR 자동 병합').length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole('button', { name: '자동조치 기본 정책' }));
    expect(screen.getByRole('combobox', { name: 'High 저장소 Critical 취약점 정책' }).value).toBe('auto_merge_pr');
  });

  it('renders organization-CVE scope counts instead of repository case summaries', () => {
    render(<WatchbackApp {...baseProps} initialView="list" isPreview={false} />);

    expect(screen.queryByText(/^\d{4}-\d{2}-\d{2} EPSS/)).toBeNull();
    expect(screen.getByText('3개 저장소 · Open Alert 2건')).not.toBeNull();
    expect(screen.queryByText('3개 Alert')).toBeNull();
    expect(screen.queryByText('Fixed 1 · 일부 해결')).toBeNull();
    expect(screen.queryByText('GHSA-f82v-jwr5-mffw')).toBeNull();
    expect(screen.queryByText(/최근 변화/)).toBeNull();
  });

  it('shows natural change labels without internal D-30 terms on the dashboard', () => {
    render(<WatchbackApp {...baseProps} initialView="dashboard" isPreview={false} />);

    expect(screen.getAllByText(/^(NEW KEV|EPSS 급등|EPSS 상위 5%)$/).length).toBeGreaterThan(0);
    expect(screen.queryByText(/EPSS D-30 급상승 조건/)).toBeNull();
  });

  it('renders the compact review summary and priority queue', () => {
    render(<WatchbackApp {...baseProps} initialView="dashboard" isPreview={false} />);

    expect(screen.getByText('Review Summary')).not.toBeNull();
    expect(screen.getByText('Priority Queue')).not.toBeNull();
    expect(screen.getByRole('button', { name: /열림 \d+/ })).not.toBeNull();
    expect(screen.getByRole('button', { name: /조치 요청됨 \d+/ })).not.toBeNull();
    expect(screen.getByRole('button', { name: /해결됨 \d+/ })).not.toBeNull();
    expect(screen.queryByText('소스 변동 영향 추정')).toBeNull();
  });

  it('renders the dashboard priority queue with vulnerability-level minimum fields', () => {
    render(<WatchbackApp {...baseProps} initialView="dashboard" isPreview={false} />);

    const queue = screen.getByTestId('priority-queue');
    expect(screen.getByText('Vulnerability')).not.toBeNull();
    expect(screen.getByText('Package')).not.toBeNull();
    expect(screen.getByText('Impact')).not.toBeNull();
    expect(screen.getByText('Change')).not.toBeNull();
    expect(within(queue).getAllByText(/^CVE-\d{4}-\d+$/).length).toBeGreaterThan(0);
    expect(within(queue).getAllByText(/개 저장소 · Open Alert \d+건$/).length).toBeGreaterThan(0);
    expect(within(queue).queryByText('Repository')).toBeNull();
    expect(within(queue).queryByText('Reason')).toBeNull();
  });

  it('uses case state for dashboard flow counts without legacy weekly KPI copy', () => {
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

    expect(screen.getByText('Review Summary')).not.toBeNull();
    expect(screen.getByText('Priority Queue')).not.toBeNull();
    expect(screen.queryByText(/지난주 대비/)).toBeNull();
    expect(screen.queryByText('8/21 ~ 8/28')).toBeNull();
  });

  it('shows one representative status badge on each priority row', () => {
    render(<WatchbackApp {...baseProps} initialView="dashboard" isPreview={false} />);

    const kevBadge = screen.getAllByText('NEW KEV')[0];
    expect(kevBadge.parentElement.children).toHaveLength(1);
    expect(screen.getAllByText(/^(NEW KEV|EPSS 급등|EPSS 상위 5%)$/).length).toBeGreaterThan(0);
  });

  it('renders candidate evidence as a dated timeline on detail', () => {
    render(<WatchbackApp {...baseProps} initialView="detail" initialSelectedId={cases[0].id} isPreview={false} />);
    expect(screen.getByRole('button', { name: '이전 화면으로' })).not.toBeNull();
    expect(screen.queryByText('검토 회차')).toBeNull();
    expect(screen.queryByText('위험 변화 재선정')).toBeNull();
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

  it('renders Gold change types naturally without raw source names', () => {
    const kevCase = cases.find((item) => item.advisory.cve_id === 'CVE-2026-42208');
    render(<WatchbackApp {...baseProps} initialView="detail" initialSelectedId={kevCase.id} isPreview={false} />);

    expect(screen.getByText('KEV 신규 등재')).not.toBeNull();
    expect(screen.queryByText('kev_new')).toBeNull();
    expect(screen.queryByText('cisa_kev')).toBeNull();
    expect(screen.queryByText('first_epss')).toBeNull();
    expect(screen.getByText('CISA에서 실제 악용 사례가 확인되었습니다.')).not.toBeNull();
  });

  it('shows repositories and alert states without review-cycle or dependency labels', () => {
    const multiRepository = cases.find((item) => item.advisory.cve_id === 'CVE-2025-29927');
    render(<WatchbackApp {...baseProps} initialView="detail" initialSelectedId={multiRepository.id} isPreview={false} />);

    expect(screen.getByText('novalink/customer-fe ↗')).not.toBeNull();
    expect(screen.getByText('novalink/commerce-web')).not.toBeNull();
    expect(screen.getByText('novalink/admin-console')).not.toBeNull();
    expect(screen.getAllByText('Demo 합성')).toHaveLength(2);
    expect(screen.getByText('처리 상태')).not.toBeNull();
    expect(screen.getByText('일부 해결')).not.toBeNull();
    expect(screen.queryByText('1건 · 일부 해결')).toBeNull();
    expect(screen.getByText('next · npm')).not.toBeNull();
    expect(screen.getByText('런타임')).not.toBeNull();
    expect(screen.getByText('>= 15.0.0, < 15.2.3')).not.toBeNull();
    expect(screen.getByText('15.2.3')).not.toBeNull();
    expect(screen.getByTestId('vulnerability-info-card')).not.toBe(
      screen.getByTestId('affected-repositories-card'),
    );
    expect(screen.queryByText('검토 회차')).toBeNull();
    expect(screen.queryByText('간접 의존성')).toBeNull();
    expect(screen.queryByText('직접 의존성')).toBeNull();
  });

  it('keeps two manifests from one repository inside one vulnerability detail', () => {
    const multiManifest = cases.find((item) => item.advisory.cve_id === 'CVE-2026-39363');
    render(<WatchbackApp {...baseProps} initialView="detail" initialSelectedId={multiManifest.id} isPreview={false} />);

    expect(screen.getByText('package-lock.json')).not.toBeNull();
    expect(screen.getByText('transitive-override/package-lock.json')).not.toBeNull();
    expect(screen.getAllByText('Open')).toHaveLength(2);
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

  it('keeps the settings page on DB and renders a three-by-four policy table', async () => {
    const onDataSourceChange = vi.fn();
    render(<WatchbackApp {...baseProps} initialView="settings" dataSource="demo" onDataSourceChange={onDataSourceChange} isPreview />);
    await waitFor(() => expect(onDataSourceChange).toHaveBeenCalledWith('db'));
    expect(screen.queryByRole('button', { name: 'Demo' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'DB' })).toBeNull();
    expect(screen.queryByText('데이터 소스')).toBeNull();
    expect(screen.queryByText('실제 운영 데이터를 사용합니다.')).toBeNull();
    expect(screen.getAllByRole('combobox')).toHaveLength(12);
    expect(screen.getByRole('combobox', { name: 'High 저장소 Critical 취약점 정책' }).value).toBe('manual_review');
    expect(screen.getByRole('combobox', { name: 'High 저장소 Medium 취약점 정책' }).value).toBe('auto_create_pr');
    expect(screen.getByRole('combobox', { name: 'Medium 저장소 Medium 취약점 정책' }).value).toBe('auto_merge_pr');
    expect(screen.getByRole('combobox', { name: 'Low 저장소 Critical 취약점 정책' }).value).toBe('auto_create_pr');
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

  it('keeps the contextual AI panel read-only outside DB mode', () => {
    render(
      <WatchbackApp
        {...baseProps}
        initialView="detail"
        initialSelectedId={cases[0].id}
        isPreview={false}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'AI 도우미 열기' }));
    const aiPanel = screen.getByLabelText('Watchback AI 도우미');
    expect(aiPanel).not.toBeNull();
    expect(document.body.classList.contains('watchback-ai-docked')).toBe(true);
    expect(within(aiPanel).getByText(new RegExp(cases[0].advisory.cve_id))).not.toBeNull();
    const detailQuestions = [
      '이 취약점들은 어떤 조건에서 문제가 되나요?',
      '우리 저장소에서 이 취약점들의 발생 조건이 확인되나요?',
      '이 업데이트로 어떤 문제가 해결되나요?',
      '업데이트할 때 확인할 변경사항이 있나요?',
    ];
    detailQuestions.forEach((question) => {
      expect(within(aiPanel).getByRole('button', { name: question })).not.toBeNull();
    });
    expect(within(aiPanel).getAllByRole('button')
      .map((button) => button.textContent)
      .filter((label) => detailQuestions.includes(label))).toEqual(detailQuestions);

    fireEvent.click(screen.getByRole('button', { name: '이 취약점들은 어떤 조건에서 문제가 되나요?' }));
    expect(screen.getByRole('alert').textContent).toContain('실제 DB 모드');

    fireEvent.click(screen.getByRole('button', { name: 'AI 도우미 닫기' }));
    expect(screen.queryByLabelText('Watchback AI 도우미')).toBeNull();
    expect(document.body.classList.contains('watchback-ai-docked')).toBe(false);
  });

  it('renders AI markdown and clears conversation after remount', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({
      answer: '**KEV** 등재 근거를 확인했습니다. [1]\n\n**Python `>=3.10,<3.14` 조건**을 확인하세요.',
      model: 'gpt-5.6-luna',
      sources: [{
        citation: '1',
        source_id: 'evidence:1',
        source_type: 'evidence',
        title: 'CISA KEV 등재',
        observed_at: '2026-05-08T00:00:00Z',
        source_url: null,
      }],
    }), { headers: { 'content-type': 'application/json' } }));
    vi.stubGlobal('fetch', fetchMock);

    const first = render(
      <WatchbackApp
        {...baseProps}
        dataSource="db"
        initialView="detail"
        initialSelectedId={cases[0].id}
        isPreview={false}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: 'AI 도우미 열기' }));
    const aiPanel = screen.getByLabelText('Watchback AI 도우미');
    fireEvent.change(screen.getByLabelText('AI 질문'), { target: { value: '핵심 근거는?' } });
    fireEvent.click(screen.getByRole('button', { name: '질문 보내기' }));
    expect(screen.getByText('핵심 근거는?')).not.toBeNull();
    expect(screen.getByRole('status').textContent).toContain('근거를 확인하고 있습니다');
    const emphasized = await screen.findByText('KEV', {}, { timeout: 3000 });
    expect(emphasized.parentElement.tagName).toBe('STRONG');
    await waitFor(() => {
      expect(aiPanel.textContent).toContain('KEV 등재 근거를 확인했습니다. [1]');
    });
    const inlineCitation = screen.getAllByText('[1]').find((element) => element.tagName === 'SUP');
    expect(inlineCitation).not.toBeNull();
    expect(inlineCitation.style.color).toBe('rgb(154, 159, 151)');
    const nestedMarkdown = await screen.findByText('>=3.10,<3.14', { selector: 'strong code' });
    expect(nestedMarkdown).not.toBeNull();
    expect(screen.queryByText('이어서 질문')).toBeNull();
    expect(screen.getByRole('button', { name: '업데이트할 때 확인할 변경사항이 있나요?' })).not.toBeNull();
    first.unmount();

    const sameContext = render(
      <WatchbackApp
        {...baseProps}
        dataSource="db"
        initialView="detail"
        initialSelectedId={cases[0].id}
        isPreview={false}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: 'AI 도우미 열기' }));
    expect(screen.queryByText(/KEV 등재 근거를 확인했습니다/)).toBeNull();
    sameContext.unmount();

    render(
      <WatchbackApp
        {...baseProps}
        dataSource="db"
        initialView="detail"
        initialSelectedId={cases[1].id}
        isPreview={false}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: 'AI 도우미 열기' }));
    expect(screen.queryByText(/KEV 등재 근거를 확인했습니다/)).toBeNull();
  });
});
