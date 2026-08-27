import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { getDemoReviewCases } from '@/lib/demo-review-cases';
import { WatchbackApp, filterAndSortCases } from './watchback-app';

const cases = getDemoReviewCases();
const baseProps = {
  initialSelectedId: null,
  initialCases: cases,
  dataSource: 'demo',
  onDataSourceChange: vi.fn(),
  loadState: 'ready',
  loadError: '',
  onRetry: vi.fn(),
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
  });

  it('renders candidate evidence as a dated timeline on detail', () => {
    render(<WatchbackApp {...baseProps} initialView="detail" initialSelectedId={cases[0].id} isPreview={false} />);
    expect(screen.getAllByText(/후보 선정/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(new RegExp(cases[0].candidates[0].evidence[0].source)).length).toBeGreaterThan(0);
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
});
