import fixture from '../../../../data/demo/vulnerability-review-groups.json';

function normalizeActivity(activity) {
  return {
    ...activity,
    actor: activity.actor ?? null,
    external_links: activity.external_links ?? [],
  };
}

function normalizeCandidate(candidate) {
  return {
    ...candidate,
    deliveries: (candidate.deliveries ?? []).map((delivery) => ({
      ...delivery,
      source_annotations: delivery.source_annotations ?? [],
    })),
    evidence: candidate.evidence ?? [],
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
    source_annotations: detail.source_annotations ?? [],
    candidates: (detail.candidates ?? [detail.latest_candidate]).map(normalizeCandidate),
    evidence: (detail.candidates ?? []).flatMap((candidate) => candidate.evidence ?? []),
    activities: (detail.activities ?? []).map(normalizeActivity),
  };
}

export function normalizeReviewCaseSummary(summary) {
  return {
    ...summary,
    source_annotations: summary.source_annotations ?? [],
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

const IMPORTANCE_ORDER = { critical: 0, high: 1, medium: 2, low: 3 };
const CANDIDATE_PRIORITY_ORDER = { P0: 0, P1: 1, P2: 2, P3: 3 };

function selectReviewPriorityCandidate(candidates, reviewCycles) {
  const activeCandidateIds = new Set(
    (reviewCycles ?? [])
      .filter((cycle) => cycle.status !== 'resolved')
      .map((cycle) => cycle.trigger_candidate_id),
  );
  const activeCandidates = candidates.filter((candidate) => (
    activeCandidateIds.size === 0 || activeCandidateIds.has(candidate.id)
  ));
  return [...activeCandidates].sort((left, right) => (
    (CANDIDATE_PRIORITY_ORDER[left.priority] ?? 99) -
      (CANDIDATE_PRIORITY_ORDER[right.priority] ?? 99) ||
    new Date(right.selected_at) - new Date(left.selected_at)
  ))[0];
}

function flattenAlerts(group) {
  return (group.affected_repositories ?? []).flatMap((repository) => (
    (repository.alerts ?? []).map((alert) => ({
      ...alert,
      repository_id: repository.id,
      repository_display_name: repository.display_name,
      repository_full_name: repository.full_name,
      repository_importance: repository.importance,
      repository_source_kind: repository.source_kind,
    }))
  ));
}

function representativeRepository(group) {
  return [...(group.affected_repositories ?? [])]
    .sort((left, right) => (
      (IMPORTANCE_ORDER[left.importance] ?? 99) -
      (IMPORTANCE_ORDER[right.importance] ?? 99)
    ))[0];
}

function adaptVulnerabilityGroup(group, includeHistory) {
  const affectedRepositories = group.affected_repositories ?? [];
  const alerts = flattenAlerts(group);
  const repository = representativeRepository(group);
  const alert = alerts.find((item) => item.state === 'open') ?? alerts[0];
  const candidates = includeHistory
    ? (group.candidates ?? []).map(normalizeCandidate)
    : [normalizeCandidate(group.latest_candidate)];
  const reviewPriorityCandidate = selectReviewPriorityCandidate(
    candidates,
    group.review_cycles,
  ) ?? normalizeCandidate(group.latest_candidate);
  const latestEvidence = includeHistory
    ? candidates.flatMap((candidate) => candidate.evidence ?? [])
    : [];
  const cycleDates = (group.review_cycles ?? []).map((cycle) => cycle.started_at).filter(Boolean);
  const openedAt = cycleDates.sort()[0] ?? group.latest_candidate.selected_at;
  const updatedAt = cycleDates.sort().at(-1) ?? group.latest_candidate.selected_at;
  const isKev = candidates.some((candidate) => (
    (candidate.evidence ?? []).some((evidence) => (
      evidence.signal === 'kev' && evidence.current_value === 'true'
    ))
  ));

  return {
    ...group,
    is_vulnerability_group: true,
    review_priority_candidate: reviewPriorityCandidate,
    group_status: group.status,
    status: group.status === 'resolved' ? 'resolved' : 'open',
    is_kev: isKev,
    review_reason: group.latest_candidate.reason_summary,
    opened_at: openedAt,
    resolved_at: group.status === 'resolved' ? updatedAt : null,
    last_reopened_at: null,
    reopened_count: 0,
    updated_at: updatedAt,
    repository,
    alert,
    alerts,
    affected_repositories: affectedRepositories,
    affected_repository_count: group.affected_repository_count,
    alert_counts: group.alert_counts,
    review_cycles: group.review_cycles ?? [],
    candidates,
    evidence: latestEvidence,
    activities: [],
    automation: {
      eligible: false,
      reason: '자동조치 기능은 아직 연결되지 않았습니다.',
      mergeMode: null,
      prUrl: null,
    },
    source_annotations: group.source_annotations ?? [],
  };
}

export function getDemoReviewCases() {
  return Object.values(fixture.details).map((group) => adaptVulnerabilityGroup(group, true));
}

export function getDemoReviewCaseSummaries() {
  return fixture.list.items.map((summary) => {
    const detail = fixture.details[summary.id];
    const adapted = adaptVulnerabilityGroup(detail, true);
    return {
      ...adapted,
      candidates: [adapted.latest_candidate],
      evidence: adapted.candidates
        .find((candidate) => candidate.id === adapted.latest_candidate.id)
        ?.evidence ?? [],
    };
  });
}

export function getDemoReviewCase(caseId) {
  const detail = fixture.details[caseId];
  return detail ? adaptVulnerabilityGroup(detail, true) : null;
}
