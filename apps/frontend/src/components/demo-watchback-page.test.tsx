import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { DATA_SOURCE_STORAGE_KEY } from '@/lib/review-case-data';
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
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({
      items: [], page: 1, page_size: 100, total: 0,
    }), { headers: { 'content-type': 'application/json' } }));
    vi.stubGlobal('fetch', fetchMock);

    render(<DemoWatchbackPage view="dashboard" />);
    expect(await screen.findByText('현재 재검토 항목이 없습니다.')).not.toBeNull();
    expect(screen.getByText('현재 DB 기준')).not.toBeNull();
    expect(screen.queryByText('Demo 데이터')).toBeNull();
    expect(screen.queryByText('지난주 대비 ▲1건')).toBeNull();
    expect(fetchMock).toHaveBeenCalledTimes(1);
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
});
