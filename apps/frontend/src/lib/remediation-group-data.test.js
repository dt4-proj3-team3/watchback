import { describe, expect, it, vi } from 'vitest';

import {
  RemediationGroupDataError,
  createRemediationPullRequests,
  closeRemediationPullRequests,
  fetchDatabaseRemediationGroups,
  loadRemediationGroups,
  normalizeDatabaseRemediationGroups,
  mergeRemediationPullRequests,
  reopenRemediationGroup,
  summarizeRemediationGroups,
} from './remediation-group-data';


function jsonResponse(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

function databaseGroup(overrides = {}) {
  return {
    id: 'group-vite',
    organization_id: '10000000-0000-0000-0000-000000000001',
    ecosystem: 'npm',
    package_name: 'vite',
    priority: 'P0',
    watchback_status: 'partially_resolved',
    github_alert_counts: {
      open: 1,
      fixed: 1,
      dismissed: 0,
      auto_dismissed: 0,
    },
    cve_count: 1,
    repository_count: 2,
    recommended_fix_versions: ['6.4.2'],
    updated_at: '2026-09-01T00:00:00Z',
    targets: [
      {
        id: 'target-a',
        repository: {
          id: '20000000-0000-0000-0000-000000000001',
          full_name: 'example/frontend',
          display_name: 'novalink/customer-fe',
          importance: 'critical',
        },
        project_root: '',
        manifest_paths: ['package.json', 'package-lock.json'],
        manifest_path: 'package-lock.json',
        watchback_status: 'needs_review',
        github_alert_counts: { open: 1, fixed: 0, dismissed: 0, auto_dismissed: 0 },
        case_ids: ['30000000-0000-0000-0000-000000000001'],
        alerts: [{
          id: '40000000-0000-0000-0000-000000000001',
          github_alert_number: 10,
          state: 'open',
          cve_id: 'CVE-2026-0042',
          ghsa_id: 'GHSA-aaaa-bbbb-cccc',
          vulnerable_version_range: '< 6.4.2',
          first_patched_version: '6.4.2',
          html_url: 'https://github.com/example/frontend/security/dependabot/10',
          github_updated_at: '2026-09-01T00:00:00Z',
        }],
      },
      {
        id: 'target-b',
        repository: {
          id: '20000000-0000-0000-0000-000000000002',
          full_name: 'example/admin',
          display_name: 'novalink/admin',
          importance: 'high',
        },
        manifest_path: 'apps/admin/package-lock.json',
        watchback_status: 'resolved',
        github_alert_counts: { open: 0, fixed: 1, dismissed: 0, auto_dismissed: 0 },
        case_ids: ['30000000-0000-0000-0000-000000000002'],
        alerts: [{
          id: '40000000-0000-0000-0000-000000000002',
          github_alert_number: 11,
          state: 'fixed',
          cve_id: 'CVE-2026-0042',
          ghsa_id: 'GHSA-aaaa-bbbb-cccc',
          vulnerable_version_range: '< 6.4.2',
          first_patched_version: '6.4.2',
          html_url: 'https://github.com/example/admin/security/dependabot/11',
          github_updated_at: '2026-08-31T00:00:00Z',
        }],
      },
    ],
    vulnerabilities: [{
      cve_id: 'CVE-2026-0042',
      ghsa_id: 'GHSA-aaaa-bbbb-cccc',
      advisory_summary: 'Vite vulnerability',
      advisory_severity: 'critical',
      priority: 'P0',
      candidate_id: '50000000-0000-0000-0000-000000000001',
      change_type: 'kev_new',
      selected_at: '2026-08-30T00:00:00Z',
      watchback_status: 'partially_resolved',
      case_ids: [
        '30000000-0000-0000-0000-000000000001',
        '30000000-0000-0000-0000-000000000002',
      ],
      alert_ids: [
        '40000000-0000-0000-0000-000000000001',
        '40000000-0000-0000-0000-000000000002',
      ],
    }],
    ...overrides,
  };
}


describe('remediation group data providers', () => {
  it('normalizes a database group into the existing C view model', () => {
    const [group] = normalizeDatabaseRemediationGroups({
      items: [databaseGroup()],
      total: 1,
    });

    expect(group).toMatchObject({
      id: 'group-vite',
      package_name: 'vite',
      priority: 'P0',
      status: 'open',
      watchback_status: 'partially_resolved',
      open_alert_count: 1,
      fixed_alert_count: 1,
      cve_count: 1,
      repository_count: 2,
      representative_patched_version: '6.4.2',
      current_version: null,
      current_versions: [],
      current_version_status: 'unavailable',
    });
    expect(group.targets).toHaveLength(2);
    expect(group.targets[0]).toMatchObject({
      project_root: '',
      manifest_paths: ['package.json', 'package-lock.json'],
    });
    expect(group.targets.every((target) => target.current_version === null)).toBe(true);
    expect(group.vulnerabilities[0]).toMatchObject({
      cve_id: 'CVE-2026-0042',
      open_alert_count: 1,
      affected_versions: ['< 6.4.2'],
      representative_patched_version: '6.4.2',
    });
    expect(group.vulnerabilities[0].candidates[0]).toMatchObject({
      change_type: 'kev_new',
      evidence: [],
      deliveries: [],
    });
  });

  it('preserves the AI summary already stored by the backend', () => {
    const aiSummary = {
      prompt_version: 'remediation-summary-v1',
      risk_summary: '5월 8일 vite의 보안 취약점이 CISA KEV에 새로 등재되었습니다.',
      action_summary: 'vite를 6.4.2 이상으로 업데이트한 뒤 애플리케이션 테스트를 수행하세요.',
      model: 'gpt-5.6-luna',
      source_ids: ['evidence:1'],
      generated_at: '2026-09-01T00:00:00Z',
    };
    const [group] = normalizeDatabaseRemediationGroups({
      items: [databaseGroup({ ai_summary: aiSummary })],
      total: 1,
    });

    expect(group.ai_summary).toEqual(aiSummary);
  });

  it('uses the backend target representative when alerts have multiple fix versions', () => {
    const raw = databaseGroup();
    raw.targets[0].alerts.push({
      ...raw.targets[0].alerts[0],
      id: '40000000-0000-0000-0000-000000000003',
      github_alert_number: 12,
      cve_id: 'CVE-2026-0043',
      first_patched_version: '6.4.3',
    });
    raw.targets[0].recommended_fix_versions = ['6.4.2', '6.4.3'];
    raw.targets[0].representative_patched_version = '6.4.3';

    const [group] = normalizeDatabaseRemediationGroups({ items: [raw], total: 1 });

    expect(group.targets[0].patched_versions).toEqual(['6.4.2', '6.4.3']);
    expect(group.targets[0].representative_patched_version).toBe('6.4.3');
  });

  it('does not invent one current version when multiple or no versions are supplied', () => {
    const noVersion = normalizeDatabaseRemediationGroups({
      items: [databaseGroup()], total: 1,
    })[0];
    const multipleVersions = normalizeDatabaseRemediationGroups({
      items: [databaseGroup({ current_versions: ['6.2.2', '6.3.0'] })], total: 1,
    })[0];

    expect(noVersion.current_version).toBeNull();
    expect(noVersion.current_version_status).toBe('unavailable');
    expect(multipleVersions.current_version).toBeNull();
    expect(multipleVersions.current_versions).toEqual(['6.2.2', '6.3.0']);
    expect(multipleVersions.current_version_status).toBe('multiple');
  });

  it('loads DB data without falling back to Demo on an error', async () => {
    const fetcher = vi.fn(async () => jsonResponse({
      code: 'backend_unavailable',
      message: 'Backend에 연결할 수 없습니다.',
      details: null,
    }, 502));

    await expect(loadRemediationGroups('db', fetcher)).rejects.toBeInstanceOf(
      RemediationGroupDataError,
    );
    expect(fetcher).toHaveBeenCalledOnce();
  });

  it('keeps the Demo fixture provider available without a network request', async () => {
    const fetcher = vi.fn();
    const groups = await loadRemediationGroups('demo', fetcher);

    expect(groups.length).toBeGreaterThan(0);
    expect(fetcher).not.toHaveBeenCalled();
  });

  it('fetches the local proxy and computes the dashboard summary', async () => {
    const fetcher = vi.fn(async (url, init) => {
      expect(url).toBe('/api/remediation-groups');
      expect(init).toEqual({ cache: 'no-store' });
      return jsonResponse({ items: [databaseGroup()], total: 1 });
    });

    const groups = await fetchDatabaseRemediationGroups(fetcher);

    expect(summarizeRemediationGroups(groups)).toEqual({
      total: 1,
      open: 1,
      accepted: 0,
      resolved: 0,
      openAlerts: 1,
    });
  });

  it('normalizes and counts accepted package groups separately', () => {
    const [group] = normalizeDatabaseRemediationGroups({
      items: [databaseGroup({ watchback_status: 'accepted' })],
      total: 1,
    });

    expect(group.status).toBe('accepted');
    expect(summarizeRemediationGroups([group])).toEqual({
      total: 1,
      open: 0,
      accepted: 1,
      resolved: 0,
      openAlerts: 1,
    });
  });

  it('requests reopening an accepted package group through the local proxy', async () => {
    const fetcher = vi.fn(async () => jsonResponse({
      group_key: 'group-vite',
      revoked_action_ids: ['action-1'],
      reopened_at: '2026-09-01T00:00:00Z',
    }));

    await expect(reopenRemediationGroup('db', 'group-vite', null, fetcher)).resolves.toMatchObject({
      revoked_action_ids: ['action-1'],
    });
    expect(fetcher).toHaveBeenCalledWith('/api/remediation-groups/group-vite/reopen', {
      method: 'POST',
      cache: 'no-store',
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
    });
  });

  it('creates and merges remediation pull requests through the local proxies', async () => {
    const createFetcher = vi.fn(async () => jsonResponse({
      id: 'action-1',
      pull_requests: [{ number: 1 }],
    }, 201));
    const mergeFetcher = vi.fn(async () => jsonResponse({
      action_id: 'action-1',
      watchback_state: 'completed',
    }));

    await createRemediationPullRequests('db', 'group-vite', ['target-1'], createFetcher);
    expect(createFetcher).toHaveBeenCalledWith('/api/remediation-groups/group-vite/pull-requests', {
      method: 'POST',
      cache: 'no-store',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target_ids: ['target-1'] }),
    });

    await mergeRemediationPullRequests('db', 'group-vite', 'action-1', mergeFetcher);
    expect(mergeFetcher).toHaveBeenCalledWith('/api/remediation-groups/group-vite/pull-requests/merge', {
      method: 'POST',
      cache: 'no-store',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action_id: 'action-1' }),
    });

    const closeFetcher = vi.fn(async () => jsonResponse({
      action_id: 'action-1',
      watchback_state: 'cancelled',
    }));
    await closeRemediationPullRequests('db', 'group-vite', 'action-1', closeFetcher);
    expect(closeFetcher).toHaveBeenCalledWith('/api/remediation-groups/group-vite/pull-requests/close', {
      method: 'POST',
      cache: 'no-store',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action_id: 'action-1' }),
    });
  });

  it('rejects malformed and duplicate backend groups', () => {
    expect(() => normalizeDatabaseRemediationGroups({ items: [], total: 1 }))
      .toThrowError(RemediationGroupDataError);
    expect(() => normalizeDatabaseRemediationGroups({
      items: [databaseGroup(), databaseGroup()],
      total: 2,
    })).toThrowError(expect.objectContaining({ code: 'duplicate_backend_group' }));
  });
});
