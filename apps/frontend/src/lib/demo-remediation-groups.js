import fixture from '../../../../data/demo/vulnerability-review-groups.json';
import reviewCaseFixture from '../../../../data/demo/review-cases.json';

const PRIORITY_ORDER = { P0: 0, P1: 1, P2: 2, P3: 3 };
const DEMO_CURRENT_VERSION = {
  Django: '4.2.20',
  bentoml: '1.4.2',
  litellm: '1.81.16',
  next: '15.2.2',
  'react-server-dom-webpack': '19.2.0',
  vite: '6.2.2',
};
const CASE_OPENED_AT_BY_ALERT_ID = new Map(
  reviewCaseFixture.list.items.map((reviewCase) => [reviewCase.alert.id, reviewCase.opened_at]),
);

function groupKey(organizationId, alert) {
  return [
    organizationId,
    alert.ecosystem,
    alert.package_name,
  ].join('|');
}

const DEPENDENCY_CONTEXT_FILES = new Set([
  'cargo.lock',
  'cargo.toml',
  'composer.json',
  'composer.lock',
  'gemfile',
  'gemfile.lock',
  'package-lock.json',
  'package.json',
  'pipfile',
  'pipfile.lock',
  'pnpm-lock.yaml',
  'poetry.lock',
  'pyproject.toml',
  'uv.lock',
  'yarn.lock',
]);

function dependencyProjectRoot(manifestPath) {
  if (!manifestPath) return '';
  const parts = manifestPath.split('/');
  if (!DEPENDENCY_CONTEXT_FILES.has(parts.at(-1).toLowerCase())) return manifestPath;
  return parts.slice(0, -1).join('/');
}

function targetKey(repository, alert) {
  return [repository.full_name, alert.ecosystem, dependencyProjectRoot(alert.manifest_path)].join('|');
}

function selectPriority(candidates = []) {
  return [...candidates].sort((left, right) => (
    (PRIORITY_ORDER[left.priority] ?? 99) - (PRIORITY_ORDER[right.priority] ?? 99) ||
    new Date(right.selected_at) - new Date(left.selected_at)
  ))[0]?.priority ?? 'P3';
}

function compareVersions(left, right) {
  return String(left).localeCompare(String(right), undefined, {
    numeric: true,
    sensitivity: 'base',
  });
}

function uniqueBy(items, keyOf) {
  const seen = new Set();
  return items.filter((item) => {
    const key = keyOf(item);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function normalizeVulnerability(detail) {
  const candidates = detail.candidates ?? [detail.latest_candidate];
  const evidence = uniqueBy(
    candidates.flatMap((candidate) => (
      (candidate.evidence ?? []).map((item) => ({
        ...item,
        candidate_id: candidate.id,
        candidate_selected_at: candidate.selected_at,
        change_type: candidate.change_type,
      }))
    )),
    (item) => [
      item.signal,
      item.observed_at,
      item.previous_value,
      item.current_value,
      item.source,
    ].join('|'),
  ).sort((left, right) => (
    new Date(left.observed_at) - new Date(right.observed_at) ||
    String(left.id).localeCompare(String(right.id))
  ));
  const sourceAnnotations = uniqueBy(
    candidates.flatMap((candidate) => (
      (candidate.deliveries ?? []).flatMap((delivery) => delivery.source_annotations ?? [])
    )),
    (item) => `${item.snapshot_date}|${item.annotation_type}`,
  ).sort((left, right) => left.snapshot_date.localeCompare(right.snapshot_date));

  return {
    id: detail.id,
    cve_id: detail.cve_id,
    ghsa_id: detail.ghsa_id,
    advisory: detail.advisory,
    priority: selectPriority(candidates),
    candidates,
    evidence,
    source_annotations: sourceAnnotations,
    alerts: [],
  };
}

export function buildDemoRemediationGroups() {
  const groups = new Map();

  Object.values(fixture.details).forEach((detail) => {
    const organization = detail.organization;
    (detail.affected_repositories ?? []).forEach((repository) => {
      (repository.alerts ?? []).forEach((alert) => {
        const key = groupKey(organization.id, alert);
        if (!groups.has(key)) {
          groups.set(key, {
            id: key,
            organization,
            ecosystem: alert.ecosystem,
            package_name: alert.package_name,
            vulnerabilities: [],
            alerts: [],
            targets: [],
          });
        }

        const group = groups.get(key);
        const actionTargetKey = targetKey(repository, alert);
        let target = group.targets.find((item) => item.id === actionTargetKey);
        if (!target) {
          target = {
            id: actionTargetKey,
            repository: {
              id: repository.id,
              full_name: repository.full_name,
              display_name: repository.display_name,
              importance: repository.importance,
              source_kind: repository.source_kind,
            },
            project_root: dependencyProjectRoot(alert.manifest_path),
            manifest_paths: [],
            manifest_path: alert.manifest_path,
            alerts: [],
          };
          group.targets.push(target);
        }
        if (alert.manifest_path && !target.manifest_paths.includes(alert.manifest_path)) {
          target.manifest_paths.push(alert.manifest_path);
          target.manifest_paths.sort();
          [target.manifest_path] = target.manifest_paths;
        }
        if (!target.alerts.some((item) => item.id === alert.id)) {
          target.alerts.push(alert);
        }
        if (!group.alerts.some((item) => item.id === alert.id)) {
          group.alerts.push(alert);
        }
        let vulnerability = group.vulnerabilities.find((item) => item.cve_id === detail.cve_id);
        if (!vulnerability) {
          vulnerability = normalizeVulnerability(detail);
          group.vulnerabilities.push(vulnerability);
        }
        if (!vulnerability.alerts.some((item) => item.id === alert.id)) {
          vulnerability.alerts.push(alert);
        }
      });
    });
  });

  return Array.from(groups.values()).map((group) => {
    const openAlerts = group.alerts.filter((alert) => alert.state === 'open');
    const fixedAlerts = group.alerts.filter((alert) => alert.state === 'fixed');
    const openAlertIds = new Set(openAlerts.map((alert) => alert.id));
    const prioritySource = group.vulnerabilities.filter((item) => (
      item.alerts.some((alert) => openAlertIds.has(alert.id))
    ));
    const priorities = (prioritySource.length ? prioritySource : group.vulnerabilities)
      .map((item) => item.priority)
      .sort((left, right) => (
        (PRIORITY_ORDER[left] ?? 99) - (PRIORITY_ORDER[right] ?? 99)
      ));
    const patchedVersions = [...new Set(group.alerts
      .map((alert) => alert.first_patched_version)
      .filter(Boolean))].sort(compareVersions);

    const vulnerabilities = [...group.vulnerabilities].map((item) => {
      const itemOpenAlerts = item.alerts.filter((alert) => alert.state === 'open');
      const affectedVersions = [...new Set(item.alerts
        .map((alert) => alert.vulnerable_version_range)
        .filter(Boolean))];
      const itemPatchedVersions = [...new Set(item.alerts
        .map((alert) => alert.first_patched_version)
        .filter(Boolean))].sort(compareVersions);
      return {
        ...item,
        alert_count: item.alerts.length,
        open_alert_count: itemOpenAlerts.length,
        affected_versions: affectedVersions,
        representative_patched_version: itemPatchedVersions.at(-1) ?? null,
      };
    }).sort((left, right) => (
      (PRIORITY_ORDER[left.priority] ?? 99) - (PRIORITY_ORDER[right.priority] ?? 99) ||
      left.cve_id.localeCompare(right.cve_id)
    ));
    const targets = group.targets.map((target) => {
      const targetOpenAlerts = target.alerts.filter((alert) => alert.state === 'open');
      const targetPatchedVersions = [...new Set(target.alerts
        .map((alert) => alert.first_patched_version)
        .filter(Boolean))].sort(compareVersions);
      return {
        ...target,
        status: targetOpenAlerts.length > 0 ? 'open' : 'resolved',
        open_alert_count: targetOpenAlerts.length,
        representative_patched_version: targetPatchedVersions.at(-1) ?? null,
        current_version: DEMO_CURRENT_VERSION[group.package_name] ?? null,
      };
    }).sort((left, right) => (
      left.repository.display_name.localeCompare(right.repository.display_name) ||
      left.project_root.localeCompare(right.project_root)
    ));

    return {
      ...group,
      vulnerabilities,
      targets,
      priority: priorities[0] ?? 'P3',
      status: openAlerts.length > 0 ? 'open' : 'resolved',
      open_alert_count: openAlerts.length,
      fixed_alert_count: fixedAlerts.length,
      cve_count: group.vulnerabilities.length,
      repository_count: new Set(targets.map((target) => target.repository.full_name)).size,
      patched_versions: patchedVersions,
      representative_patched_version: patchedVersions.at(-1) ?? null,
      registered_at: group.alerts
        .map((alert) => CASE_OPENED_AT_BY_ALERT_ID.get(alert.id))
        .filter(Boolean)
        .sort()
        .at(0) ?? null,
      current_version: DEMO_CURRENT_VERSION[group.package_name] ?? null,
      updated_at: group.alerts
        .map((alert) => alert.github_updated_at)
        .filter(Boolean)
        .sort()
        .at(-1) ?? null,
    };
  }).sort((left, right) => (
    (PRIORITY_ORDER[left.priority] ?? 99) - (PRIORITY_ORDER[right.priority] ?? 99) ||
    left.package_name.localeCompare(right.package_name)
  ));
}

export function summarizeDemoRemediationGroups(groups = buildDemoRemediationGroups()) {
  return {
    total: groups.length,
    open: groups.filter((group) => group.status === 'open').length,
    accepted: groups.filter((group) => group.status === 'accepted').length,
    resolved: groups.filter((group) => group.status === 'resolved').length,
    openAlerts: groups.reduce((sum, group) => sum + group.open_alert_count, 0),
  };
}
