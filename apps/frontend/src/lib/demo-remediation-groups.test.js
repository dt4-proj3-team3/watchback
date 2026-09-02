import { describe, expect, it } from 'vitest';

import {
  buildDemoRemediationGroups,
  summarizeDemoRemediationGroups,
} from './demo-remediation-groups';

describe('demo remediation groups', () => {
  const groups = buildDemoRemediationGroups();

  it('groups the fixture by organization, ecosystem, and package', () => {
    expect(groups).toHaveLength(6);
    expect(summarizeDemoRemediationGroups(groups)).toEqual({
      total: 6,
      open: 6,
      accepted: 0,
      resolved: 0,
      openAlerts: 11,
    });
    expect(new Set(groups.map((group) => group.id)).size).toBe(6);
  });

  it('groups multiple vulnerabilities for the same package action', () => {
    const vite = groups.find((group) => group.package_name === 'vite');
    const litellm = groups.find((group) => group.package_name === 'litellm');

    expect(vite.vulnerabilities.map((item) => item.cve_id)).toEqual([
      'CVE-2025-31125',
      'CVE-2025-31486',
      'CVE-2026-39363',
    ]);
    expect(vite.representative_patched_version).toBe('6.4.2');
    expect(vite.current_version).toBe('6.2.2');
    expect(litellm.vulnerabilities).toHaveLength(2);
    expect(litellm.representative_patched_version).toBe('1.83.7');
    expect(litellm.current_version).toBe('1.81.16');
  });

  it('keeps repositories and manifests as action targets inside a package', () => {
    const next = groups.find((group) => group.package_name === 'next');
    const vite = groups.find((group) => group.package_name === 'vite');

    expect(next.targets).toHaveLength(3);
    expect(next.repository_count).toBe(3);
    expect(new Set(next.targets.map((target) => target.repository.display_name))).toEqual(new Set([
      'novalink/admin-console',
      'novalink/commerce-web',
      'novalink/customer-fe',
    ]));
    expect(vite.targets).toHaveLength(2);
    expect(vite.repository_count).toBe(1);
    expect(new Set(vite.targets.map((target) => target.manifest_path))).toEqual(new Set([
      'package-lock.json',
      'transitive-override/package-lock.json',
    ]));
  });

  it('does not duplicate alerts or evidence inside a group', () => {
    groups.forEach((group) => {
      expect(new Set(group.alerts.map((alert) => alert.id)).size).toBe(group.alerts.length);
      group.targets.forEach((target) => {
        expect(new Set(target.alerts.map((alert) => alert.id)).size).toBe(target.alerts.length);
      });
      expect(new Set(group.vulnerabilities.map((item) => item.cve_id)).size)
        .toBe(group.vulnerabilities.length);
      group.vulnerabilities.forEach((item) => {
        expect(new Set(item.alerts.map((alert) => alert.id)).size).toBe(item.alerts.length);
        const keys = item.evidence.map((evidence) => [
          evidence.signal,
          evidence.observed_at,
          evidence.previous_value,
          evidence.current_value,
          evidence.source,
        ].join('|'));
        expect(new Set(keys).size).toBe(keys.length);
      });
    });
  });
});
