import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { getDemoReviewCases } from '@/lib/demo-review-cases';
import { WatchbackApp, filterAndSortCases } from './watchback-app';

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

  it('shows persistent KEV status before EPSS and stale badges on the dashboard', () => {
    render(<WatchbackApp {...baseProps} initialView="dashboard" isPreview={false} />);

    const kevBadge = screen.getAllByText('KEV')[0];
    const badgeRow = kevBadge.parentElement;
    const labels = [...badgeRow.children].map((element) => element.textContent);

    expect(labels[0]).toBe('KEV');
    expect(labels[1]).toMatch(/^(EPSS 급등|상위 5%)$/);
    expect(labels[2]).toMatch(/일째 미처리$/);
  });

  it('renders candidate evidence as a dated timeline on detail', () => {
    render(<WatchbackApp {...baseProps} initialView="detail" initialSelectedId={cases[0].id} isPreview={false} />);
    expect(screen.getByRole('button', { name: '이전 화면으로' })).not.toBeNull();
    expect(screen.getAllByText(/후보 선정/).length).toBeGreaterThan(0);
    expect(screen.getByText('향후 30일 악용 가능성')).not.toBeNull();
  });

  it('renders Gold change types naturally without raw sources or duplicate dates', () => {
    const kevCase = cases.find((item) => item.candidates.some((candidate) => candidate.change_type === 'kev_new'));
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
