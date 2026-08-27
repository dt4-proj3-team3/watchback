import { describe, expect, it } from 'vitest';

import { getDemoReviewCaseSummaries } from './demo-review-cases';
import {
  DATA_SOURCE_STORAGE_KEY,
  ReviewCaseDataError,
  fetchDatabaseReviewCases,
  loadReviewCase,
  readStoredDataSource,
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
});
