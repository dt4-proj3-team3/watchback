import fixture from '../../../../data/demo/review-cases.json';

export function getDemoReviewCases() {
  return Object.values(fixture.details).map((detail) => ({
    ...detail,
    automation: {
      eligible: false,
      reason: '데모 Fixture에는 자동조치 결과가 포함되지 않습니다.',
      mergeMode: null,
      prUrl: null,
    },
    candidates: detail.candidates.map((candidate) => ({
      change_type: candidate.change_type,
      reason_summary: candidate.reason_summary,
      selected_at: candidate.selected_at,
    })),
    evidence: detail.candidates.flatMap((candidate) => candidate.evidence),
    activities: detail.activities.map((activity) => ({
      ...activity,
      actor: activity.actor ?? null,
      external_link: activity.external_link ?? null,
    })),
  }));
}

export function hasDemoReviewCase(caseId) {
  return Object.hasOwn(fixture.details, caseId);
}
