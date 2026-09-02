import {
  buildDemoRemediationGroups,
  summarizeDemoRemediationGroups,
} from './demo-remediation-groups';


export class RemediationGroupDataError extends Error {
  constructor(message, status = 500, code = 'remediation_group_data_error') {
    super(message);
    this.name = 'RemediationGroupDataError';
    this.status = status;
    this.code = code;
  }
}

function unique(items) {
  return [...new Set(items.filter((item) => item != null && item !== ''))];
}

function readCurrentVersions(value) {
  if (!Array.isArray(value)) return [];
  return unique(value.filter((item) => typeof item === 'string'));
}

function currentVersionFields(raw) {
  const currentVersions = readCurrentVersions(raw?.current_versions);
  return {
    current_versions: currentVersions,
    current_version: currentVersions.length === 1 ? currentVersions[0] : null,
    current_version_status: raw?.current_version_status ?? (currentVersions.length === 0
      ? 'unavailable'
      : currentVersions.length === 1 ? 'resolved' : 'multiple'),
    current_version_reason: raw?.current_version_reason ?? null,
  };
}

function alertCounts(raw) {
  const counts = raw?.github_alert_counts ?? {};
  return {
    open: Number.isInteger(counts.open) ? counts.open : 0,
    fixed: Number.isInteger(counts.fixed) ? counts.fixed : 0,
    dismissed: Number.isInteger(counts.dismissed) ? counts.dismissed : 0,
    auto_dismissed: Number.isInteger(counts.auto_dismissed) ? counts.auto_dismissed : 0,
  };
}

function uiStatus(watchbackStatus) {
  if (watchbackStatus === 'resolved') return 'resolved';
  if (watchbackStatus === 'accepted') return 'accepted';
  return 'open';
}

function representativeFixVersion(raw, versions) {
  if (typeof raw?.representative_patched_version === 'string') {
    return raw.representative_patched_version;
  }
  return versions.length === 1 ? versions[0] : null;
}

function normalizeAlert(raw) {
  return {
    id: raw.id,
    github_alert_number: raw.github_alert_number,
    state: raw.state,
    cve_id: raw.cve_id,
    ghsa_id: raw.ghsa_id,
    vulnerable_version_range: raw.vulnerable_version_range,
    first_patched_version: raw.first_patched_version ?? null,
    html_url: raw.html_url,
    github_updated_at: raw.github_updated_at,
    source_kind: raw.source_kind ?? 'actual',
  };
}

function normalizeTarget(raw) {
  const alerts = (raw.alerts ?? []).map(normalizeAlert);
  const counts = alertCounts(raw);
  const patchedVersions = unique(
    Array.isArray(raw.recommended_fix_versions)
      ? raw.recommended_fix_versions
      : alerts.map((alert) => alert.first_patched_version),
  );
  return {
    id: raw.id,
    repository: { ...raw.repository, source_kind: raw.repository?.source_kind ?? 'actual' },
    project_root: raw.project_root ?? '',
    manifest_paths: Array.isArray(raw.manifest_paths)
      ? unique(raw.manifest_paths)
      : raw.manifest_path ? [raw.manifest_path] : [],
    manifest_path: raw.manifest_path ?? null,
    status: uiStatus(raw.watchback_status),
    watchback_status: raw.watchback_status,
    github_alert_counts: counts,
    open_alert_count: counts.open,
    case_ids: raw.case_ids ?? [],
    alerts,
    patched_versions: patchedVersions,
    representative_patched_version: representativeFixVersion(raw, patchedVersions),
    ...currentVersionFields(raw),
  };
}

function normalizeVulnerability(raw, alertsById) {
  const alerts = (raw.alert_ids ?? [])
    .map((alertId) => alertsById.get(alertId))
    .filter(Boolean);
  const patchedVersions = unique(
    alerts.map((alert) => alert.first_patched_version),
  );
  const affectedVersions = unique(
    alerts.map((alert) => alert.vulnerable_version_range),
  );
  const rawCandidates = Array.isArray(raw.candidates) && raw.candidates.length > 0
    ? raw.candidates
    : [{
        id: raw.candidate_id,
        cve_id: raw.cve_id,
        ghsa_id: raw.ghsa_id,
        priority: raw.priority,
        change_type: raw.change_type,
        selected_at: raw.selected_at,
        reason_summary: raw.reason_summary ?? raw.advisory_summary,
        evidence: raw.evidence ?? [],
        deliveries: raw.deliveries ?? [],
      }];
  const candidates = rawCandidates.map((candidate) => ({
    ...candidate,
    evidence: Array.isArray(candidate.evidence) ? candidate.evidence : [],
    deliveries: Array.isArray(candidate.deliveries) ? candidate.deliveries : [],
  }));
  const evidence = candidates.flatMap((candidate) => candidate.evidence);
  return {
    id: raw.cve_id,
    cve_id: raw.cve_id,
    ghsa_id: raw.ghsa_id,
    advisory: {
      ghsa_id: raw.ghsa_id,
      cve_id: raw.cve_id,
      summary: raw.advisory_summary,
      severity: raw.advisory_severity,
      cvss_score: raw.cvss_score ?? null,
    },
    priority: raw.priority,
    watchback_status: raw.watchback_status,
    case_ids: raw.case_ids ?? [],
    candidates,
    evidence,
    source_annotations: Array.isArray(raw.source_annotations)
      ? raw.source_annotations
      : [],
    alerts,
    alert_count: alerts.length,
    open_alert_count: alerts.filter((alert) => alert.state === 'open').length,
    affected_versions: affectedVersions,
    representative_patched_version: representativeFixVersion(raw, patchedVersions),
  };
}

export function normalizeDatabaseRemediationGroup(raw) {
  if (
    !raw ||
    typeof raw.id !== 'string' ||
    typeof raw.package_name !== 'string' ||
    typeof raw.ecosystem !== 'string' ||
    !Array.isArray(raw.targets) ||
    !Array.isArray(raw.vulnerabilities)
  ) {
    throw new RemediationGroupDataError(
      '패키지 조치 후보 응답 형식이 올바르지 않습니다.',
      502,
      'invalid_backend_response',
    );
  }

  const targets = raw.targets.map(normalizeTarget);
  const alerts = targets.flatMap((target) => target.alerts);
  const alertsById = new Map(alerts.map((alert) => [alert.id, alert]));
  const counts = alertCounts(raw);
  const patchedVersions = unique(
    Array.isArray(raw.recommended_fix_versions)
      ? raw.recommended_fix_versions
      : alerts.map((alert) => alert.first_patched_version),
  );
  return {
    id: raw.id,
    organization: { id: raw.organization_id },
    organization_id: raw.organization_id,
    ecosystem: raw.ecosystem,
    package_name: raw.package_name,
    priority: raw.priority,
    status: uiStatus(raw.watchback_status),
    watchback_status: raw.watchback_status,
    github_alert_counts: counts,
    open_alert_count: counts.open,
    fixed_alert_count: counts.fixed,
    cve_count: raw.cve_count,
    repository_count: raw.repository_count,
    patched_versions: patchedVersions,
    representative_patched_version: representativeFixVersion(raw, patchedVersions),
    registered_at: raw.registered_at,
    updated_at: raw.updated_at,
    ai_summary: raw.ai_summary ?? null,
    action_history: Array.isArray(raw.action_history) ? raw.action_history : [],
    targets,
    alerts,
    vulnerabilities: raw.vulnerabilities.map((item) => (
      normalizeVulnerability(item, alertsById)
    )),
    ...currentVersionFields(raw),
  };
}

export function normalizeDatabaseRemediationGroups(body) {
  if (
    !body ||
    !Array.isArray(body.items) ||
    !Number.isInteger(body.total) ||
    body.total < 0 ||
    body.items.length !== body.total
  ) {
    throw new RemediationGroupDataError(
      '패키지 조치 후보 목록 응답 형식이 올바르지 않습니다.',
      502,
      'invalid_backend_response',
    );
  }
  const groups = body.items.map(normalizeDatabaseRemediationGroup);
  if (new Set(groups.map((group) => group.id)).size !== groups.length) {
    throw new RemediationGroupDataError(
      '패키지 조치 후보 ID가 중복되었습니다.',
      502,
      'duplicate_backend_group',
    );
  }
  return groups;
}

async function readJsonResponse(response) {
  let body = null;
  try {
    body = await response.json();
  } catch {
    // The proxy sanitizes non-JSON upstream failures.
  }
  if (!response.ok) {
    throw new RemediationGroupDataError(
      body?.message ?? '패키지 조치 후보를 불러오지 못했습니다.',
      response.status,
      body?.code ?? 'remediation_group_data_error',
    );
  }
  return body;
}

export async function fetchDatabaseRemediationGroups(fetcher = fetch) {
  const response = await fetcher('/api/remediation-groups', { cache: 'no-store' });
  return normalizeDatabaseRemediationGroups(await readJsonResponse(response));
}

export async function loadRemediationGroups(source, fetcher = fetch) {
  if (source === 'demo') return buildDemoRemediationGroups();
  if (source === 'db') return fetchDatabaseRemediationGroups(fetcher);
  throw new TypeError('지원하지 않는 데이터 소스입니다.');
}

export async function createRemediationAction(source, groupId, payload, fetcher = fetch) {
  if (source === 'demo') {
    throw new RemediationGroupDataError(
      'Demo 데이터에서는 조치 기록을 저장하지 않습니다.',
      403,
      'demo_read_only',
    );
  }
  const response = await fetcher(
    `/api/remediation-groups/${encodeURIComponent(groupId)}/actions`,
    {
      method: 'POST',
      cache: 'no-store',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
  );
  return readJsonResponse(response);
}

export async function createRemediationPullRequests(source, groupId, targetIds = null, fetcher = globalThis.fetch) {
  if (source === 'demo') {
    throw new RemediationGroupDataError(
      'Demo 데이터에서는 업데이트 PR을 생성하지 않습니다.',
      403,
      'demo_read_only',
    );
  }
  const response = await fetcher(
    `/api/remediation-groups/${encodeURIComponent(groupId)}/pull-requests`,
    {
      method: 'POST',
      cache: 'no-store',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(targetIds?.length ? { target_ids: targetIds } : {}),
    },
  );
  return readJsonResponse(response);
}

export async function mergeRemediationPullRequests(source, groupId, actionId, fetcher = globalThis.fetch) {
  if (source === 'demo') {
    throw new RemediationGroupDataError(
      'Demo 데이터에서는 업데이트 PR을 병합하지 않습니다.',
      403,
      'demo_read_only',
    );
  }
  const response = await fetcher(
    `/api/remediation-groups/${encodeURIComponent(groupId)}/pull-requests/merge`,
    {
      method: 'POST',
      cache: 'no-store',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action_id: actionId }),
    },
  );
  return readJsonResponse(response);
}

export async function closeRemediationPullRequests(source, groupId, actionId, fetcher = globalThis.fetch) {
  if (source === 'demo') {
    throw new RemediationGroupDataError(
      'Demo 데이터에서는 업데이트 PR을 닫지 않습니다.',
      403,
      'demo_read_only',
    );
  }
  const response = await fetcher(
    `/api/remediation-groups/${encodeURIComponent(groupId)}/pull-requests/close`,
    {
      method: 'POST',
      cache: 'no-store',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action_id: actionId }),
    },
  );
  return readJsonResponse(response);
}

export async function reopenRemediationGroup(source, groupId, targetIds = null, fetcher = fetch) {
  if (source === 'demo') {
    throw new RemediationGroupDataError(
      'Demo 데이터에서는 재검토 상태를 변경하지 않습니다.',
      403,
      'demo_read_only',
    );
  }
  const response = await fetcher(
    `/api/remediation-groups/${encodeURIComponent(groupId)}/reopen`,
    {
      method: 'POST',
      cache: 'no-store',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(targetIds?.length ? { target_ids: targetIds } : {}),
    },
  );
  return readJsonResponse(response);
}

export function summarizeRemediationGroups(groups, source = 'db') {
  if (source === 'demo') return summarizeDemoRemediationGroups(groups);
  return {
    total: groups.length,
    open: groups.filter((group) => group.status === 'open').length,
    accepted: groups.filter((group) => group.status === 'accepted').length,
    resolved: groups.filter((group) => group.status === 'resolved').length,
    openAlerts: groups.reduce((sum, group) => sum + group.open_alert_count, 0),
  };
}
