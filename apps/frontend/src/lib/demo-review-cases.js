import fixture from '../../../../data/demo/review-cases.json';

function normalizeActivity(activity) {
  return {
    ...activity,
    actor: activity.actor ?? null,
    external_links: activity.external_links ?? [],
  };
}

export function normalizeReviewCaseDetail(detail) {
  return {
    ...detail,
    automation: {
      eligible: false,
      reason: '자동조치 기능은 아직 연결되지 않았습니다.',
      mergeMode: null,
      prUrl: null,
    },
    candidates: detail.candidates ?? [detail.latest_candidate],
    evidence: (detail.candidates ?? []).flatMap((candidate) => candidate.evidence ?? []),
    activities: (detail.activities ?? []).map(normalizeActivity),
  };
}

export function normalizeReviewCaseSummary(summary) {
  return {
    ...summary,
    automation: {
      eligible: false,
      reason: '자동조치 기능은 아직 연결되지 않았습니다.',
      mergeMode: null,
      prUrl: null,
    },
    candidates: [summary.latest_candidate],
    evidence: [],
    activities: [],
  };
}

export function getDemoReviewCases() {
  return Object.values(fixture.details).map(normalizeReviewCaseDetail);
}

export function getDemoReviewCaseSummaries() {
  return fixture.list.items.map(normalizeReviewCaseSummary);
}

export function getDemoReviewCase(caseId) {
  const detail = fixture.details[caseId];
  return detail ? normalizeReviewCaseDetail(detail) : null;
}
