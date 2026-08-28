import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { DATA_SOURCE_STORAGE_KEY } from '@/lib/review-case-data';
import { getDemoReviewCases } from '@/lib/demo-review-cases';
import { DemoWatchbackPage } from './demo-watchback-page';

describe('review page data source selection', () => {
  it('loads db by default and renders an empty response without demo fallback', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({
      items: [], page: 1, page_size: 100, total: 0,
    }), { headers: { 'content-type': 'application/json' } }));
    vi.stubGlobal('fetch', fetchMock);

    render(<DemoWatchbackPage view="list" />);
    expect(await screen.findByText('현재 조건에 맞는 재검토 후보가 없습니다')).not.toBeNull();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(screen.queryByText('Demo 데이터')).toBeNull();
  });

  it('uses the db response for the dashboard instead of demo cases', async () => {
    const fetchMock = vi.fn(async (url) => new Response(JSON.stringify(
      url === '/api/review-cases/dashboard-summary'
        ? {
          reference_at: '2026-08-28T00:00:00Z',
          previous_reference_at: '2026-08-21T00:00:00Z',
          critical_open: { current_count: 0, previous_count: 0, delta: 0 },
          stale_open: { current_count: 0, previous_count: 0, delta: 0 },
          source_impact_open: { current_count: 0, previous_count: 0, delta: 0 },
        }
        : { items: [], page: 1, page_size: 100, total: 0 },
    ), { headers: { 'content-type': 'application/json' } }));
    vi.stubGlobal('fetch', fetchMock);

    render(<DemoWatchbackPage view="dashboard" />);
    expect(await screen.findByText('현재 재검토 항목이 없습니다.')).not.toBeNull();
    expect(screen.getByText('8/21 ~ 8/28')).not.toBeNull();
    expect(screen.getByText('지금 봐야 할 항목과 이번 주 위험 변화 흐름을 한눈에 확인하세요.')).not.toBeNull();
    expect(screen.getByText('이번 주 처리 흐름')).not.toBeNull();
    expect(screen.queryByText('Demo 데이터')).toBeNull();
    expect(screen.queryByText('지난주 대비 ▲1건')).toBeNull();
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock).toHaveBeenCalledWith('/api/review-cases/dashboard-summary', {
      cache: 'no-store',
    });
  });

  it('uses the db response for repositories instead of demo cases', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({
      items: [], page: 1, page_size: 100, total: 0,
    }), { headers: { 'content-type': 'application/json' } })));

    render(<DemoWatchbackPage view="repos" />);
    expect(await screen.findByText('재검토 Case가 연결된 저장소가 없습니다.')).not.toBeNull();
    expect(screen.queryByText('novalink/customer-fe')).toBeNull();
  });

  it('uses and marks an explicit demo choice', async () => {
    localStorage.setItem(DATA_SOURCE_STORAGE_KEY, 'demo');
    render(<DemoWatchbackPage view="list" />);
    expect(await screen.findByText('Demo 데이터')).not.toBeNull();
    expect(screen.getAllByRole('button').length).toBeGreaterThan(0);
  });

  it('loads demo cases on the dashboard only when demo is explicitly selected', async () => {
    localStorage.setItem(DATA_SOURCE_STORAGE_KEY, 'demo');
    render(<DemoWatchbackPage view="dashboard" />);
    expect(await screen.findByText('Demo 데이터')).not.toBeNull();
    expect(screen.getAllByText('novalink/customer-fe').length).toBeGreaterThan(0);
  });

  it('stores demo risk acceptance and PR links in page memory without an API call', async () => {
    const reviewCase = getDemoReviewCases()[0];
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    localStorage.setItem(DATA_SOURCE_STORAGE_KEY, 'demo');

    render(<DemoWatchbackPage view="detail" selectedId={reviewCase.id} />);
    await screen.findByRole('button', { name: '위험 수용' });
    fireEvent.click(screen.getByRole('button', { name: '위험 수용' }));
    fireEvent.change(screen.getByLabelText('활동 메모'), {
      target: { value: '업데이트 PR을 연결했습니다.' },
    });
    fireEvent.change(screen.getByLabelText('외부 링크 유형'), {
      target: { value: 'pull_request' },
    });
    fireEvent.change(screen.getByLabelText('외부 링크 URL'), {
      target: { value: 'https://github.com/novalink/customer-fe/pull/21' },
    });
    fireEvent.click(screen.getByRole('button', { name: '기록하기' }));

    const link = await screen.findByRole('link', { name: '연결된 PR ↗' });
    expect(link.getAttribute('href')).toBe('https://github.com/novalink/customer-fe/pull/21');
    expect(screen.getByText(/김서연 ·/)).not.toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('keeps db selected when loading fails', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({
      code: 'backend_unavailable', message: 'Backend에 연결할 수 없습니다.', details: null,
    }), { status: 502, headers: { 'content-type': 'application/json' } })));
    render(<DemoWatchbackPage view="list" />);
    expect(await screen.findByText('Backend에 연결할 수 없습니다.')).not.toBeNull();
    expect(screen.queryByText('Demo 데이터')).toBeNull();
    expect(localStorage.getItem(DATA_SOURCE_STORAGE_KEY)).toBeNull();
  });

  it('persists only a settings choice made by the user', async () => {
    render(<DemoWatchbackPage view="settings" />);
    fireEvent.click(screen.getByRole('button', { name: 'Demo' }));
    await waitFor(() => expect(localStorage.getItem(DATA_SOURCE_STORAGE_KEY)).toBe('demo'));
  });

  it('refetches server truth after recording an activity', async () => {
    const original = getDemoReviewCases()[0];
    const activity = {
      id: '70000000-0000-0000-0000-000000000001',
      candidate_id: original.latest_candidate.id,
      activity_type: 'risk_accepted',
      note: '검토 후 위험을 수용합니다.',
      actor: {
        id: '7889d975-3d64-536f-8740-3d0a28ee3a1d',
        display_name: '김서연',
      },
      occurred_at: '2026-08-27T03:00:00Z',
      created_at: '2026-08-27T03:00:00Z',
      external_links: [],
    };
    const resolved = {
      ...original,
      status: 'resolved',
      resolved_at: activity.occurred_at,
      updated_at: activity.occurred_at,
      activities: [...original.activities, activity],
    };
    let recorded = false;
    const fetchMock = vi.fn(async (_url, init = {}) => {
      if (init.method === 'POST') {
        recorded = true;
        return new Response(JSON.stringify({ case_status: 'resolved', activity }), {
          status: 201,
          headers: { 'content-type': 'application/json' },
        });
      }
      return new Response(JSON.stringify(recorded ? resolved : original), {
        headers: { 'content-type': 'application/json' },
      });
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<DemoWatchbackPage view="detail" selectedId={original.id} />);
    await screen.findByRole('button', { name: '위험 수용' });
    fireEvent.click(screen.getByRole('button', { name: '위험 수용' }));
    fireEvent.change(screen.getByLabelText('활동 메모'), {
      target: { value: activity.note },
    });
    fireEvent.click(screen.getByRole('button', { name: '기록하기' }));

    expect(await screen.findByText('해결됨')).not.toBeNull();
    expect(screen.getByText('김서연 · 2026.08.27')).not.toBeNull();
    expect(screen.getByText(activity.note)).not.toBeNull();
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(1);
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method !== 'POST')).toHaveLength(2);
  });
});
