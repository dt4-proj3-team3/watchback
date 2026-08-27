import {
  getDemoReviewCase,
  getDemoReviewCaseSummaries,
  normalizeReviewCaseDetail,
  normalizeReviewCaseSummary,
} from './demo-review-cases';

export const DATA_SOURCE_STORAGE_KEY = 'watchback.dataSource';
const DATA_SOURCE_EVENT = 'watchback:data-source-change';

export class ReviewCaseDataError extends Error {
  constructor(message, status = 500, code = 'review_case_data_error') {
    super(message);
    this.name = 'ReviewCaseDataError';
    this.status = status;
    this.code = code;
  }
}

export function readStoredDataSource(storage) {
  const value = storage.getItem(DATA_SOURCE_STORAGE_KEY);
  return value === 'demo' || value === 'db' ? value : 'db';
}

export function storeDataSource(storage, source) {
  if (source !== 'demo' && source !== 'db') {
    throw new TypeError('지원하지 않는 데이터 소스입니다.');
  }
  storage.setItem(DATA_SOURCE_STORAGE_KEY, source);
  window.dispatchEvent(new Event(DATA_SOURCE_EVENT));
}

export function subscribeToDataSource(callback) {
  const onStorage = (event) => {
    if (!event.key || event.key === DATA_SOURCE_STORAGE_KEY) callback();
  };
  window.addEventListener('storage', onStorage);
  window.addEventListener(DATA_SOURCE_EVENT, callback);
  return () => {
    window.removeEventListener('storage', onStorage);
    window.removeEventListener(DATA_SOURCE_EVENT, callback);
  };
}

async function readJsonResponse(response) {
  let body = null;
  try {
    body = await response.json();
  } catch {
    // The proxy sanitizes upstream failures. Keep client errors generic.
  }
  if (!response.ok) {
    throw new ReviewCaseDataError(
      body?.message ?? '재검토 데이터를 불러오지 못했습니다.',
      response.status,
      body?.code ?? 'review_case_data_error',
    );
  }
  return body;
}

function assertListPage(page, expectedPage) {
  if (
    !page ||
    !Array.isArray(page.items) ||
    page.page !== expectedPage ||
    !Number.isInteger(page.total) ||
    page.total < 0
  ) {
    throw new ReviewCaseDataError('재검토 목록 응답 형식이 올바르지 않습니다.', 502, 'invalid_backend_response');
  }
}

export async function fetchDatabaseReviewCases(fetcher = fetch) {
  const items = [];
  const seenIds = new Set();
  let pageNumber = 1;
  let total = null;

  while (total === null || items.length < total) {
    const response = await fetcher(`/api/review-cases?status=all&page=${pageNumber}&page_size=100`, {
      cache: 'no-store',
    });
    const page = await readJsonResponse(response);
    assertListPage(page, pageNumber);

    if (total !== null && page.total !== total) {
      throw new ReviewCaseDataError('목록 조회 중 전체 건수가 변경되었습니다.', 502, 'unstable_backend_response');
    }
    total = page.total;
    if (page.items.length === 0 && items.length < total) {
      throw new ReviewCaseDataError('목록 페이지 조회가 완료되지 않았습니다.', 502, 'incomplete_backend_response');
    }
    if (page.items.some((item) => !item?.id || seenIds.has(item.id))) {
      throw new ReviewCaseDataError('목록 페이지가 반복되거나 Case ID가 중복되었습니다.', 502, 'repeated_backend_page');
    }

    page.items.forEach((item) => seenIds.add(item.id));
    items.push(...page.items);
    pageNumber += 1;
    if (pageNumber > 100) {
      throw new ReviewCaseDataError('재검토 목록 페이지 제한을 초과했습니다.', 502, 'backend_page_limit_exceeded');
    }
  }

  return items.slice(0, total).map(normalizeReviewCaseSummary);
}

export async function fetchDatabaseReviewCase(caseId, fetcher = fetch) {
  const response = await fetcher(`/api/review-cases/${encodeURIComponent(caseId)}`, {
    cache: 'no-store',
  });
  const detail = await readJsonResponse(response);
  return normalizeReviewCaseDetail(detail);
}

export async function loadReviewCases(source, fetcher = fetch) {
  return source === 'demo' ? getDemoReviewCaseSummaries() : fetchDatabaseReviewCases(fetcher);
}

export async function loadReviewCase(source, caseId, fetcher = fetch) {
  if (source === 'demo') {
    const detail = getDemoReviewCase(caseId);
    if (!detail) {
      throw new ReviewCaseDataError('재검토 Case를 찾을 수 없습니다.', 404, 'review_case_not_found');
    }
    return detail;
  }
  return fetchDatabaseReviewCase(caseId, fetcher);
}
