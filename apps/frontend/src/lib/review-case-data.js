import {
  getDemoReviewCase,
  getDemoReviewCaseSummaries,
  normalizeReviewCaseDetail,
  normalizeReviewCaseSummary,
} from './demo-review-cases';

export const DATA_SOURCE_STORAGE_KEY = 'watchback.dataSource';
const DATA_SOURCE_EVENT = 'watchback:data-source-change';
let demoActivityStore = {};
const DEMO_ACTOR = {
  id: '7889d975-3d64-536f-8740-3d0a28ee3a1d',
  display_name: '김서연',
};

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

export function resetDemoActivities() {
  demoActivityStore = {};
}

function applyDemoActivities(reviewCase) {
  const added = demoActivityStore[reviewCase.id] ?? [];
  if (added.length === 0) return reviewCase;
  const activities = [...(reviewCase.activities ?? []), ...added]
    .sort((left, right) => new Date(left.occurred_at) - new Date(right.occurred_at));
  const acceptance = [...activities]
    .reverse()
    .find((activity) => activity.activity_type === 'risk_accepted');
  const latest = activities.at(-1);
  return {
    ...reviewCase,
    status: acceptance ? 'resolved' : reviewCase.status,
    resolved_at: acceptance?.occurred_at ?? reviewCase.resolved_at,
    updated_at: latest?.occurred_at ?? reviewCase.updated_at,
    activities,
  };
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

export async function createReviewActivity(
  source,
  caseId,
  payload,
  fetcher = fetch,
) {
  if (source === 'demo') {
    const reviewCase = getDemoReviewCase(caseId);
    if (!reviewCase) {
      throw new ReviewCaseDataError('재검토 Case를 찾을 수 없습니다.', 404, 'review_case_not_found');
    }
    const activities = [...(reviewCase.activities ?? []), ...(demoActivityStore[caseId] ?? [])];
    if (activities.some((activity) => (
      activity.candidate_id === payload.candidate_id &&
      activity.activity_type === payload.activity_type
    ))) {
      throw new ReviewCaseDataError(
        '현재 후보에 같은 활동이 이미 기록되어 있습니다.',
        409,
        'duplicate_activity',
      );
    }
    const url = payload.external_link?.url;
    if (url && Object.values(demoActivityStore).flat().some((activity) => (
      activity.external_links?.some((link) => link.url === url)
    ))) {
      throw new ReviewCaseDataError(
        '이미 연결된 GitHub Issue 또는 PR입니다.',
        409,
        'duplicate_external_link',
      );
    }
    const now = new Date().toISOString();
    const activityId = crypto.randomUUID();
    const externalLinks = url ? [{
      id: crypto.randomUUID(),
      link_type: payload.external_link.link_type,
      url,
      github_owner: new URL(url).pathname.split('/')[1],
      github_repository: new URL(url).pathname.split('/')[2],
      github_number: Number(new URL(url).pathname.split('/')[4]),
      external_state: null,
      github_updated_at: null,
      last_synced_at: null,
    }] : [];
    const activity = {
      id: activityId,
      candidate_id: payload.candidate_id,
      activity_type: payload.activity_type,
      note: payload.note ?? null,
      actor: DEMO_ACTOR,
      occurred_at: now,
      created_at: now,
      external_links: externalLinks,
    };
    demoActivityStore[caseId] = [...(demoActivityStore[caseId] ?? []), activity];
    return {
      case_status: payload.activity_type === 'risk_accepted' ? 'resolved' : reviewCase.status,
      activity,
    };
  }
  const response = await fetcher(`/api/review-cases/${encodeURIComponent(caseId)}`, {
    method: 'POST',
    cache: 'no-store',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return readJsonResponse(response);
}

export async function loadReviewCases(source, fetcher = fetch) {
  return source === 'demo'
    ? getDemoReviewCaseSummaries().map((reviewCase) => applyDemoActivities(reviewCase))
    : fetchDatabaseReviewCases(fetcher);
}

export async function loadReviewCase(source, caseId, fetcher = fetch) {
  if (source === 'demo') {
    const detail = getDemoReviewCase(caseId);
    if (!detail) {
      throw new ReviewCaseDataError('재검토 Case를 찾을 수 없습니다.', 404, 'review_case_not_found');
    }
    return applyDemoActivities(detail);
  }
  return fetchDatabaseReviewCase(caseId, fetcher);
}
