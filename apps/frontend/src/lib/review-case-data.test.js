import { describe, expect, it, vi } from 'vitest';

import { getDemoReviewCaseSummaries } from './demo-review-cases';
import {
  DATA_SOURCE_STORAGE_KEY,
  ReviewCaseDataError,
  createReviewActivity,
  fetchDatabaseDashboardSummary,
  fetchDatabaseReviewCases,
  loadReviewCases,
  loadReviewCase,
  readStoredDataSource,
  resetDemoActivities,
  storeDataSource,
} from './review-case-data';

function jsonResponse(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

describe('review case data providers', () => {
  it('uses db by default and stores only an explicit valid choice', () => {
    expect(readStoredDataSource(localStorage)).toBe('db');
    localStorage.setItem(DATA_SOURCE_STORAGE_KEY, 'unexpected');
    expect(readStoredDataSource(localStorage)).toBe('db');
    storeDataSource(localStorage, 'demo');
    expect(readStoredDataSource(localStorage)).toBe('demo');
    expect(() => storeDataSource(localStorage, 'invalid')).toThrow(TypeError);
  });

  it('walks every backend page without requesting detail endpoints', async () => {
    const summaries = getDemoReviewCaseSummaries().slice(0, 3);
    const urls = [];
    const fetcher = async (url) => {
      urls.push(url);
      const page = urls.length;
      return jsonResponse({
        items: page === 1 ? summaries.slice(0, 2) : summaries.slice(2),
        page,
        page_size: 100,
        total: 3,
      });
    };

    const cases = await fetchDatabaseReviewCases(fetcher);
    expect(cases.map((item) => item.id)).toEqual(summaries.map((item) => item.id));
    expect(urls).toEqual([
      '/api/review-cases?status=all&page=1&page_size=100',
      '/api/review-cases?status=all&page=2&page_size=100',
    ]);
    expect(cases.every((item) => item.evidence.length === 0)).toBe(true);
  });

  it('loads one demo review item per organization and CVE', async () => {
    const summaries = getDemoReviewCaseSummaries();
    const grouped = await loadReviewCases('demo');
    expect(summaries).toHaveLength(9);
    expect(grouped).toHaveLength(9);
    expect(new Set(grouped.map((item) => (
      `${item.organization.id}:${item.advisory.cve_id}`
    ))).size).toBe(9);
  });

  it('rejects a page sequence that cannot make progress', async () => {
    await expect(fetchDatabaseReviewCases(async () => jsonResponse({
      items: [], page: 1, page_size: 100, total: 1,
    }))).rejects.toMatchObject({ code: 'incomplete_backend_response' });
  });

  it('rejects repeated cases across backend pages', async () => {
    const summary = getDemoReviewCaseSummaries()[0];
    let page = 0;
    await expect(fetchDatabaseReviewCases(async () => {
      page += 1;
      return jsonResponse({ items: [summary], page, page_size: 100, total: 2 });
    })).rejects.toMatchObject({ code: 'repeated_backend_page' });
  });

  it('returns a typed 404 for a missing demo detail', async () => {
    await expect(loadReviewCase('demo', 'missing')).rejects.toEqual(
      expect.objectContaining({ status: 404, code: 'review_case_not_found' }),
    );
  });

  it('does not turn backend errors into demo data', async () => {
    await expect(fetchDatabaseReviewCases(async () => jsonResponse({
      code: 'backend_unavailable', message: 'Backend에 연결할 수 없습니다.', details: null,
    }, 502))).rejects.toBeInstanceOf(ReviewCaseDataError);
  });

  it('loads the database dashboard weekly comparison without demo fallback', async () => {
    const summary = {
      reference_at: '2026-08-28T00:00:00Z',
      previous_reference_at: '2026-08-21T00:00:00Z',
      critical_open: { current_count: 4, previous_count: 2, delta: 2 },
      stale_open: { current_count: 1, previous_count: 2, delta: -1 },
      source_impact_open: { current_count: 3, previous_count: 0, delta: 3 },
    };
    const fetcher = vi.fn(async (url) => {
      expect(url).toBe('/api/review-cases/dashboard-summary');
      return jsonResponse(summary);
    });

    await expect(fetchDatabaseDashboardSummary(fetcher)).resolves.toEqual(summary);
    expect(fetcher).toHaveBeenCalledOnce();
  });

  it('posts a db activity and preserves contract errors', async () => {
    const payload = {
      activity_type: 'note_added',
      candidate_id: '10000000-0000-0000-0000-000000000001',
      note: '확인 메모',
    };
    const fetcher = async (url, init) => {
      expect(url).toBe('/api/review-cases/case-id');
      expect(init.method).toBe('POST');
      expect(JSON.parse(init.body)).toEqual(payload);
      return jsonResponse({ case_status: 'open', activity: { id: 'activity-id' } }, 201);
    };
    await expect(createReviewActivity('db', 'case-id', payload, fetcher)).resolves.toMatchObject({
      case_status: 'open',
    });

    await expect(createReviewActivity('db', 'case-id', payload, async () => jsonResponse({
      code: 'duplicate_activity', message: '중복 활동', details: null,
    }, 409))).rejects.toMatchObject({ status: 409, code: 'duplicate_activity' });
  });

  it('stores demo activities only in the current page runtime', async () => {
    const fetcher = vi.fn();
    const reviewCase = getDemoReviewCaseSummaries()[0];
    const originalDetail = await loadReviewCase('demo', reviewCase.id, fetcher);
    const payload = {
      activity_type: 'external_link_added',
      candidate_id: reviewCase.latest_candidate.id,
      external_link: {
        link_type: 'pull_request',
        url: 'https://github.com/novalink/customer-fe/pull/21',
      },
    };
    await expect(createReviewActivity('demo', reviewCase.id, payload, fetcher)).resolves.toMatchObject({
      case_status: reviewCase.status,
      activity: {
        candidate_id: reviewCase.latest_candidate.id,
        activity_type: 'external_link_added',
        actor: { display_name: '김서연' },
      },
    });
    expect(fetcher).not.toHaveBeenCalled();
    const detail = await loadReviewCase('demo', reviewCase.id, fetcher);
    expect(detail.activities.at(-1)).toMatchObject({
      activity_type: 'external_link_added',
      external_links: [{
        link_type: 'pull_request',
        url: 'https://github.com/novalink/customer-fe/pull/21',
      }],
    });

    resetDemoActivities();
    const reloaded = await loadReviewCase('demo', reviewCase.id, fetcher);
    expect(reloaded.activities).toEqual(originalDetail.activities);
    expect(reloaded.status).toBe(originalDetail.status);
  });
});
