import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { buildDemoRemediationGroups } from '@/lib/demo-remediation-groups';
import * as remediationGroupData from '@/lib/remediation-group-data';
import { RemediationPreviewPage } from './remediation-preview-page';

describe('remediation C preview', () => {
  beforeEach(() => {
    window.localStorage.setItem('watchback.dataSource', 'demo');
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders package-based dashboard metrics and queue columns', async () => {
    render(<RemediationPreviewPage view="dashboard" onNavigate={vi.fn()} />);

    expect(await screen.findByText('Review Summary')).not.toBeNull();
    expect(screen.queryByRole('button', { name: '조치 후보' })).toBeNull();
    expect(screen.getByText('Issues').parentElement.textContent).toContain('6');
    expect(screen.queryByText('Grouped Issues')).toBeNull();
    expect(Number(screen.getByText('KEV 포함').parentElement.querySelector('strong').textContent)).toBeGreaterThan(0);
    expect(screen.getByText('위험 수용').parentElement.textContent).toContain('0');
    expect(screen.getByText('해결됨').parentElement.textContent).toContain('0');
    expect(screen.queryByText('Open Alert')).toBeNull();
    expect(screen.getByText('우선순위')).not.toBeNull();
    expect(screen.getByText('패키지')).not.toBeNull();
    expect(screen.getByText('핵심 취약점')).not.toBeNull();
    expect(screen.getByText('CVE')).not.toBeNull();
    expect(screen.queryByText('Repository')).toBeNull();
    expect(screen.getByText('저장소 · Open Alert')).not.toBeNull();
    expect(screen.getByText('변화')).not.toBeNull();
    expect(screen.getByText('권장 수정 버전')).not.toBeNull();
    expect(screen.getAllByText('NEW KEV').length).toBeGreaterThan(0);
    expect(screen.getAllByText('SQLi').length).toBeGreaterThan(0);
    expect(screen.getAllByText('RCE').length).toBeGreaterThan(0);
    expect(screen.getAllByText(/최근 변화 \d{2}\.\d{2}/).length).toBeGreaterThan(0);
    expect(within(screen.getByTestId('remediation-priority-queue')).queryByText('검토 필요')).toBeNull();
    expect(screen.queryByRole('button', { name: 'DB' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Demo' })).toBeNull();
  });

  it('opens the selected package in the separate candidate route', async () => {
    const navigate = vi.fn();
    render(<RemediationPreviewPage view="dashboard" onNavigate={navigate} />);

    const queue = await screen.findByTestId('remediation-priority-queue');
    const packageRow = within(queue).getAllByRole('button')[0];
    fireEvent.click(packageRow);

    expect(navigate).toHaveBeenCalledWith(expect.stringMatching(
      /^\/review-cases\//,
    ));
  });

  it('filters the candidate list to the repository selected on the repository page', async () => {
    const groups = buildDemoRemediationGroups();
    const repository = groups[0].targets[0].repository;
    const expectedGroups = groups.filter((group) => group.targets.some((target) => (
      target.repository.full_name === repository.full_name
    )));

    render(
      <RemediationPreviewPage
        view="list"
        initialRepositoryFullName={repository.full_name}
        onNavigate={vi.fn()}
      />,
    );

    const repositoryFilter = await screen.findByRole('button', {
      name: `저장소: ${repository.display_name} ×`,
    });
    expect(document.querySelectorAll('.watchback-remediation-row')).toHaveLength(expectedGroups.length);

    fireEvent.click(repositoryFilter);
    expect(document.querySelectorAll('.watchback-remediation-row')).toHaveLength(groups.length);
  });

  it('classifies arbitrary command execution advisories as RCE', async () => {
    const group = buildDemoRemediationGroups()[0];
    const commandExecutionGroup = {
      ...group,
      id: 'opencode-command-execution',
      package_name: 'opencode-ai',
      vulnerabilities: [{
        ...group.vulnerabilities[0],
        advisory: {
          ...group.vulnerabilities[0].advisory,
          summary: "OpenCode's Unauthenticated HTTP Server Allows Arbitrary Command Execution",
        },
      }],
    };
    vi.spyOn(remediationGroupData, 'loadRemediationGroups').mockResolvedValue([
      commandExecutionGroup,
    ]);

    render(<RemediationPreviewPage view="list" onNavigate={vi.fn()} />);

    expect(await screen.findByText('RCE')).not.toBeNull();
    expect(screen.queryByText('-')).toBeNull();
  });

  it('renders the stored DB summary without calling the AI review endpoint', async () => {
    window.localStorage.setItem('watchback.dataSource', 'db');
    const group = {
      ...buildDemoRemediationGroups()[0],
      ai_summary: {
        prompt_version: 'remediation-summary-v3',
        risk_summary: 'SQL 주입 취약점으로, 5월 8일 CISA가 실제 악용이 확인된 취약점으로 KEV에 새로 등재했습니다.',
        action_summary: 'litellm 패키지를 1.83.10 이상으로 업데이트한 뒤 애플리케이션 테스트를 수행하세요.',
        interpretation_note: '5월 8일 EPSS 모델·소스 변동과 겹쳐 소스 변동 영향이 함께 반영됐을 수 있습니다.',
      },
    };
    vi.spyOn(remediationGroupData, 'loadRemediationGroups').mockResolvedValue([group]);
    const fetchSpy = vi.spyOn(globalThis, 'fetch');

    render(<RemediationPreviewPage view="list" initialExpandedGroupId={group.id} onNavigate={vi.fn()} />);

    const summary = await screen.findByRole('region', { name: 'AI 요약' });
    expect(within(summary).getByText('SQL 주입').tagName).toBe('STRONG');
    expect(within(summary).getByText('KEV').tagName).toBe('STRONG');
    expect(within(summary).getByText('해석 주의')).not.toBeNull();
    expect(summary.textContent).toContain('EPSS 모델·소스 변동과 겹쳐');
    expect(within(summary).queryByText('권장 조치')).toBeNull();
    expect(within(summary).queryByText(group.ai_summary.action_summary)).toBeNull();
    expect(fetchSpy).not.toHaveBeenCalledWith(
      expect.stringContaining('/api/ai/review'),
      expect.anything(),
    );
  });

  it('expands all CVE evidence inline without navigating to the B detail', async () => {
    const groups = buildDemoRemediationGroups();
    const vite = groups.find((group) => group.package_name === 'vite');
    const navigate = vi.fn();
    const back = vi.fn();

    render(
      <RemediationPreviewPage
        view="list"
        initialExpandedGroupId={vite.id}
        onNavigate={navigate}
        onBack={back}
      />,
    );

    const detail = await screen.findByTestId('remediation-detail-vite');
    expect(within(detail).getByText('변화 근거')).not.toBeNull();
    expect(within(detail).getByText(/검토 대상 등록 2026\.08\./)).not.toBeNull();
    const timeline = within(detail).getByRole('region', { name: '변화 타임라인' });
    expect(timeline).not.toBeNull();
    expect(within(detail).queryByRole('region', { name: 'EPSS 변화' })).toBeNull();
    fireEvent.mouseEnter(within(timeline).getByRole('button', { name: /CVE-2025-31125, EPSS 급등/ }));
    expect(within(timeline).getByText('CVE-2025-31125')).not.toBeNull();
    expect(within(timeline).getByText(/↑ EPSS \+7\.6%p/)).not.toBeNull();
    const timelineEvent = within(timeline).getByRole('button', { name: /CVE-2025-31125, EPSS 급등/ });
    fireEvent.click(timelineEvent);
    expect(detail.querySelector('.watchback-remediation-cve-row[aria-expanded="true"]')?.textContent).toContain('CVE-2025-31125');
    fireEvent.click(timelineEvent);
    expect(detail.querySelector('.watchback-remediation-cve-row[aria-expanded="true"]')).toBeNull();
    expect(detail.querySelector('.watchback-remediation-cve-head').textContent).toBe('CVEChange영향 버전Fix');
    expect(within(detail).getByText('vite · npm')).not.toBeNull();
    expect(within(detail).getAllByText('권장 수정 버전').length).toBeGreaterThan(0);
    expect(within(detail).queryByText('패키지 정보')).toBeNull();
    expect(within(detail).getByText('조치 대상')).not.toBeNull();
    expect(within(detail).queryByText('검토 활동')).toBeNull();
    expect(within(detail).queryByText('REPOSITORY')).toBeNull();
    expect(within(detail).queryByText('CVE 3건을 해결하기 위해 패키지 1건을 조치해야 합니다.')).toBeNull();
    expect(within(detail).queryByText(/CVE 3건을 함께 검토합니다/)).toBeNull();
    expect(within(detail).getByRole('button', { name: '전체 위험 수용' })).not.toBeNull();
    expect(within(detail).getAllByRole('button', { name: '위험 수용' })).toHaveLength(2);
    expect(within(detail).getByRole('button', { name: '전체 조치' })).not.toBeNull();
    expect(within(detail).getAllByRole('button', { name: '조치하기' })).toHaveLength(2);
    expect(within(detail).queryByText('CVE 3건')).toBeNull();
    expect(within(detail).queryByText('저장소 1곳')).toBeNull();
    expect(within(detail).getByText('transitive-override/package-lock.json')).not.toBeNull();
    const alertToggles = within(detail).getAllByRole('button', { name: /Open Alert 1건/ });
    fireEvent.click(alertToggles[0]);
    expect(within(detail).getByText('Dependabot #106').parentElement.textContent).toContain('CVE-2026-39363');
    expect(within(detail).getByRole('link', { name: 'GitHub에서 보기 ↗' })).not.toBeNull();
    expect(detail.querySelectorAll('.watchback-remediation-cve-row[aria-expanded="false"]')).toHaveLength(3);
    expect(detail.querySelector('.watchback-remediation-cve-row[aria-expanded="true"]')).toBeNull();
    expect(screen.queryByText('litellm')).toBeNull();
    expect(within(detail).getAllByText('CVE-2025-31125').length).toBeGreaterThanOrEqual(2);
    expect(within(detail).getByText('CVE-2025-31486')).not.toBeNull();
    expect(within(detail).getAllByText('CVE-2026-39363').length).toBeGreaterThanOrEqual(2);
    fireEvent.click(Array.from(detail.querySelectorAll('.watchback-remediation-cve-row')).find((row) => row.textContent.includes('CVE-2025-31125')));
    expect(within(detail).getAllByText('향후 30일 악용 가능성').length).toBeGreaterThan(0);
    expect(within(detail).getByRole('link', { name: 'CVE 상세 ↗' }).getAttribute('href')).toContain('CVE-2025-31125');
    expect(within(detail).getByRole('link', { name: 'GitHub Advisory ↗' }).getAttribute('href')).toContain('GHSA-');

    fireEvent.click(Array.from(detail.querySelectorAll('.watchback-remediation-cve-row')).find((row) => row.textContent.includes('CVE-2025-31486')));
    expect(within(detail).getByText(/EPSS 모델 v5 전환일/)).not.toBeNull();
    expect(within(detail).getAllByRole('link', { name: '출처 보기 ↗' }).length).toBeGreaterThan(0);
    expect(within(detail).queryByText('first_epss')).toBeNull();
    expect(within(detail).queryByText('cisa_kev')).toBeNull();
    expect(navigate).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: '이전 화면으로' }));
    expect(back).toHaveBeenCalledTimes(1);
    expect(navigate).not.toHaveBeenCalled();
  });

  it('shows the timeline when the group has only one evidence event', async () => {
    window.localStorage.setItem('watchback.dataSource', 'db');
    const baseGroup = buildDemoRemediationGroups()[0];
    const vulnerability = baseGroup.vulnerabilities[0];
    const candidate = vulnerability.candidates[0];
    const group = {
      ...baseGroup,
      vulnerabilities: [{
        ...vulnerability,
        candidates: [{
          ...candidate,
          evidence: candidate.evidence.slice(0, 1),
          deliveries: [],
        }],
      }],
    };
    vi.spyOn(remediationGroupData, 'loadRemediationGroups').mockResolvedValue([group]);

    render(<RemediationPreviewPage view="list" initialExpandedGroupId={group.id} onNavigate={vi.fn()} />);

    expect(await screen.findByRole('region', { name: '변화 타임라인' })).not.toBeNull();
  });

  it('keeps Demo group actions read-only without mutating fixture state', async () => {
    const group = buildDemoRemediationGroups()[0];
    render(<RemediationPreviewPage view="list" initialExpandedGroupId={group.id} onNavigate={vi.fn()} />);

    fireEvent.click(await screen.findByRole('button', { name: '전체 위험 수용' }));
    const riskDialog = screen.getByRole('dialog', { name: '위험 수용' });
    expect(within(riskDialog).getByRole('radio', { name: '호환성 문제로 보류' })).not.toBeNull();
    expect(within(riskDialog).getByRole('radio', { name: '현재 영향 낮음' })).not.toBeNull();
    expect(within(riskDialog).getByRole('radio', { name: '기타' })).not.toBeNull();
    expect(within(riskDialog).queryByRole('textbox')).toBeNull();
    fireEvent.click(within(riskDialog).getByRole('radio', { name: '기타' }));
    expect(within(riskDialog).getByRole('textbox', { name: '기타 사유' })).not.toBeNull();
    fireEvent.click(within(riskDialog).getByRole('button', { name: '취소' }));

    fireEvent.click(await screen.findByRole('button', { name: '전체 조치' }));
    const dialog = screen.getByRole('dialog', { name: '업데이트 PR 생성' });
    expect(within(dialog).getByText(/프로젝트에 업데이트 PR을 생성합니다/)).not.toBeNull();
    expect(within(dialog).queryByRole('button', { name: '닫기' })).toBeNull();
    fireEvent.click(within(dialog).getByRole('button', { name: 'PR 일괄 생성' }));
    expect((await screen.findByRole('status')).textContent).toContain('Demo 데이터에서는 업데이트 PR을 생성하지 않습니다.');
    expect(screen.getByText(/검토 필요/)).not.toBeNull();

    fireEvent.click(screen.getByRole('button', { name: '조치하기' }));
    const targetDialog = screen.getByRole('dialog', { name: '업데이트 PR 생성' });
    expect(within(targetDialog).getByText('1개 저장소의 1개 프로젝트에 업데이트 PR을 생성합니다.')).not.toBeNull();
    expect(within(targetDialog).getByRole('button', { name: 'PR 생성' })).not.toBeNull();
    expect(within(targetDialog).queryByText('GitHub Issue 생성')).toBeNull();
  });

  it('creates and merges pull requests through explicit button stages', async () => {
    window.localStorage.setItem('watchback.dataSource', 'db');
    const group = buildDemoRemediationGroups()[0];
    vi.spyOn(remediationGroupData, 'loadRemediationGroups').mockResolvedValue([group]);
    const apiFetcher = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({
        id: 'action-1',
        pull_requests: [{ number: 1 }, { number: 2 }],
      }), { status: 201, headers: { 'content-type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        action_id: 'action-1',
        watchback_state: 'completed',
        pull_requests: [{ number: 1, merged: true }, { number: 2, merged: true }],
        alert_verifications: [],
      }), { status: 200, headers: { 'content-type': 'application/json' } }));

    render(<RemediationPreviewPage view="list" initialExpandedGroupId={group.id} onNavigate={vi.fn()} apiFetcher={apiFetcher} />);

    fireEvent.click(await screen.findByRole('button', { name: '전체 조치' }));
    const dialog = screen.getByRole('dialog', { name: '업데이트 PR 생성' });
    expect(within(dialog).getByRole('button', { name: '모달 닫기' }).textContent).toBe('×');
    expect(within(dialog).queryByRole('button', { name: '취소' })).toBeNull();
    fireEvent.click(within(dialog).getByRole('button', { name: 'PR 일괄 생성' }));
    await waitFor(() => expect(within(dialog).getByText('✓ PR 2개 생성 완료')).not.toBeNull());
    expect(apiFetcher).toHaveBeenNthCalledWith(1, `/api/remediation-groups/${encodeURIComponent(group.id)}/pull-requests`, expect.objectContaining({ method: 'POST' }));

    expect(within(dialog).getByRole('button', { name: 'PR 일괄 닫기' })).not.toBeNull();
    fireEvent.click(within(dialog).getByRole('button', { name: 'PR 일괄 병합' }));
    await waitFor(() => expect(within(dialog).getByRole('button', { name: '✓ 조치 완료' })).not.toBeNull());
    expect(apiFetcher).toHaveBeenNthCalledWith(2, `/api/remediation-groups/${encodeURIComponent(group.id)}/pull-requests/merge`, expect.objectContaining({ method: 'POST', body: JSON.stringify({ action_id: 'action-1' }) }));
  });

  it('does not render an alert toggle when a target has no open alerts', async () => {
    window.localStorage.setItem('watchback.dataSource', 'db');
    const baseGroup = buildDemoRemediationGroups()[0];
    const target = {
      ...baseGroup.targets[0],
      status: 'resolved',
      open_alert_count: 0,
      alerts: baseGroup.targets[0].alerts.map((alert) => ({ ...alert, state: 'fixed' })),
    };
    const group = {
      ...baseGroup,
      status: 'resolved',
      open_alert_count: 0,
      targets: [target],
    };
    vi.spyOn(remediationGroupData, 'loadRemediationGroups').mockResolvedValue([group]);

    render(<RemediationPreviewPage view="list" initialExpandedGroupId={group.id} onNavigate={vi.fn()} />);

    const detail = await screen.findByTestId(`remediation-detail-${group.package_name}`);
    expect(within(detail).getAllByText('0건').length).toBeGreaterThan(0);
    expect(within(detail).queryByRole('button', { name: /Open Alert 0건/ })).toBeNull();
  });

  it('shows bulk close and merge actions when pull requests are already open', async () => {
    window.localStorage.setItem('watchback.dataSource', 'db');
    const baseGroup = buildDemoRemediationGroups()[0];
    const group = {
      ...baseGroup,
      action_history: [{
        id: 'action-open-prs',
        event_type: 'remediation_requested',
        watchback_state: 'pr_open',
        target_count: 2,
        pull_requests: [
          { number: 1, url: 'https://github.com/example/a/pull/1', merged: false, closed: false },
          { number: 2, url: 'https://github.com/example/b/pull/2', merged: false, closed: false },
        ],
      }],
    };
    vi.spyOn(remediationGroupData, 'loadRemediationGroups').mockResolvedValue([group]);

    render(<RemediationPreviewPage view="list" initialExpandedGroupId={group.id} onNavigate={vi.fn()} />);

    fireEvent.click(await screen.findByRole('button', { name: '전체 조치' }));
    const dialog = screen.getByRole('dialog', { name: '업데이트 PR 생성' });
    expect(within(dialog).queryByRole('button', { name: 'PR 일괄 생성' })).toBeNull();
    expect(within(dialog).getByRole('button', { name: 'PR 일괄 닫기' })).not.toBeNull();
    expect(within(dialog).getByRole('button', { name: 'PR 일괄 병합' })).not.toBeNull();
    expect(within(dialog).getByText('✓ PR 2개 생성 완료')).not.toBeNull();
  });

  it('stores a structured acceptance reason and refreshes the DB group', async () => {
    window.localStorage.setItem('watchback.dataSource', 'db');
    const group = { ...buildDemoRemediationGroups()[0], status: 'open' };
    vi.spyOn(remediationGroupData, 'loadRemediationGroups').mockResolvedValue([group]);
    const createAction = vi.spyOn(remediationGroupData, 'createRemediationAction')
      .mockResolvedValue({ targets: [{ alert_id: 'alert-1' }] });

    render(<RemediationPreviewPage view="list" initialExpandedGroupId={group.id} onNavigate={vi.fn()} />);

    const targetSection = (await screen.findByText('조치 대상')).closest('section');
    fireEvent.click(within(targetSection).getByRole('button', { name: '위험 수용' }));
    const dialog = screen.getByRole('dialog', { name: '위험 수용' });
    fireEvent.click(within(dialog).getByRole('radio', { name: '호환성 문제로 보류' }));
    fireEvent.click(within(dialog).getByRole('button', { name: '위험 수용' }));

    await waitFor(() => expect(createAction).toHaveBeenCalledWith('db', group.id, {
      action_type: 'risk_accepted',
      target_ids: [group.targets[0].id],
      reason_code: 'compatibility_blocked',
      note: null,
    }));
    await waitFor(() => expect(remediationGroupData.loadRemediationGroups).toHaveBeenCalledTimes(2));
  });

  it('shows only reopen and remediation actions for an accepted DB group', async () => {
    window.localStorage.setItem('watchback.dataSource', 'db');
    const group = {
      ...buildDemoRemediationGroups()[0],
      status: 'accepted',
      targets: buildDemoRemediationGroups()[0].targets.map((target) => ({
        ...target,
        status: 'accepted',
      })),
      action_history: [{
        id: 'action-1',
        event_type: 'risk_accepted',
        watchback_state: 'accepted',
        reason_code: 'compatibility_blocked',
        note: null,
        actor_user_id: 'user-1',
        actor_display_name: '김보안',
        occurred_at: '2026-09-01T05:20:00Z',
        target_count: 2,
      }],
    };
    vi.spyOn(remediationGroupData, 'loadRemediationGroups').mockResolvedValue([group]);
    const reopen = vi.spyOn(remediationGroupData, 'reopenRemediationGroup')
      .mockResolvedValue({ revoked_action_ids: ['action-1'] });

    render(<RemediationPreviewPage view="list" initialExpandedGroupId={group.id} onNavigate={vi.fn()} />);

    expect(await screen.findByTestId(`remediation-detail-${group.package_name}`)).not.toBeNull();
    expect(screen.queryByRole('button', { name: '위험 수용' })).toBeNull();
    expect(screen.getByRole('button', { name: '전체 조치' })).not.toBeNull();
    expect(screen.getByRole('button', { name: '전체 재검토 열기' })).not.toBeNull();
    const history = screen.getByRole('region', { name: '조치 이력' });
    expect(within(history).getByText('위험 수용 · 전체')).not.toBeNull();
    expect(within(history).getByText('호환성 문제로 보류')).not.toBeNull();
    expect(within(history).getByText((_, node) => (
      node?.textContent === '2026.09.01 14:20 · 김보안'
    ))).not.toBeNull();
    expect(within(history).queryByRole('button', { name: '더보기' })).toBeNull();
    expect(within(history).getAllByText('위험 수용 · 전체')).toHaveLength(1);
    fireEvent.click(screen.getByRole('button', { name: '재검토 열기' }));
    const dialog = screen.getByRole('dialog', { name: '재검토 열기' });
    expect(within(dialog).getByText(`${group.targets[0].repository.display_name} 저장소를 다시 검토 필요 상태로 변경합니다.`)).not.toBeNull();
    expect(reopen).not.toHaveBeenCalled();
    fireEvent.click(within(dialog).getByRole('button', { name: '재검토 열기' }));

    await waitFor(() => expect(reopen).toHaveBeenCalledWith('db', group.id, [group.targets[0].id]));
    await waitFor(() => expect(remediationGroupData.loadRemediationGroups).toHaveBeenCalledTimes(2));
  });

  it('shows each remediation PR only on its matching target card', async () => {
    window.localStorage.setItem('watchback.dataSource', 'db');
    const baseGroup = buildDemoRemediationGroups()[0];
    const target = baseGroup.targets[0];
    const group = {
      ...baseGroup,
      action_history: [{
        id: 'action-pr-1',
        event_type: 'remediation_requested',
        watchback_state: 'completed',
        actor_display_name: '김보안',
        occurred_at: '2026-09-01T15:12:00Z',
        target_count: 1,
        pull_requests: [{
          repository_full_name: target.repository.full_name,
          project_root: target.project_root,
          number: 6,
          url: 'https://github.com/example/repository/pull/6',
          target_version: '7.5.2',
        }, {
          repository_full_name: target.repository.full_name,
          project_root: target.project_root,
          number: 7,
          url: 'https://github.com/example/repository/pull/7',
          target_version: '7.5.2',
          closed: true,
        }],
      }],
    };
    vi.spyOn(remediationGroupData, 'loadRemediationGroups').mockResolvedValue([group]);

    render(<RemediationPreviewPage view="list" initialExpandedGroupId={group.id} onNavigate={vi.fn()} />);

    const history = await screen.findByRole('region', { name: '조치 이력' });
    expect(within(history).getByText('7.5.2 업데이트')).not.toBeNull();
    expect(within(history).queryByRole('link', { name: 'PR #6 ↗' })).toBeNull();
    const targetSection = screen.getByText('조치 대상').closest('section');
    const link = within(targetSection).getByRole('link', { name: 'PR #6 ↗' });
    expect(link.getAttribute('href')).toBe('https://github.com/example/repository/pull/6');
    expect(within(targetSection).queryByRole('link', { name: 'PR #7 ↗' })).toBeNull();
  });

  it('uses KEV as the representative change when a CVE also has a later EPSS candidate', async () => {
    const group = buildDemoRemediationGroups().find((item) => (
      item.vulnerabilities.some((vulnerability) => vulnerability.cve_id === 'CVE-2026-42208')
    ));

    render(<RemediationPreviewPage view="list" initialExpandedGroupId={group.id} onNavigate={vi.fn()} />);

    const cve = await screen.findByRole('button', { name: /CVE-2026-42208.*NEW KEV/ });
    expect(cve).not.toBeNull();
    fireEvent.click(cve);
    expect(screen.getByText('CISA에서 실제 악용 사례가 확인되었습니다.')).not.toBeNull();
  });

  it('uses the original EPSS percentage-point explanation in the evidence card', async () => {
    const group = buildDemoRemediationGroups().find((item) => (
      item.vulnerabilities.some((vulnerability) => vulnerability.cve_id === 'CVE-2026-35029')
    ));

    render(<RemediationPreviewPage view="list" initialExpandedGroupId={group.id} onNavigate={vi.fn()} />);

    const detail = await screen.findByTestId(`remediation-detail-${group.package_name}`);
    fireEvent.click(Array.from(detail.querySelectorAll('.watchback-remediation-cve-row')).find((row) => row.textContent.includes('CVE-2026-35029')));
    expect(screen.getByText('30일 전보다 13%p 상승했습니다.')).not.toBeNull();
  });

  it('filters package candidates without changing the B review routes', async () => {
    render(<RemediationPreviewPage view="list" onNavigate={vi.fn()} />);

    await screen.findByRole('button', { name: '열림' });
    expect(screen.getByText('변화 유형')).not.toBeNull();
    expect(screen.getByText('저장소 중요도')).not.toBeNull();
    expect(['우선순위 순', '최근 업데이트 순', '생성일 순'].map((name) => screen.getByRole('button', { name }).textContent)).toEqual([
      '우선순위 순', '최근 업데이트 순', '생성일 순',
    ]);
    fireEvent.click(screen.getByRole('button', { name: '우선순위 순' }));
    expect(screen.getAllByRole('button').filter((button) => button.classList.contains('watchback-remediation-row'))[0].textContent).toContain('Critical');
    fireEvent.click(screen.getByRole('button', { name: '생성일 순' }));
    expect(screen.getByText('Django')).not.toBeNull();
    expect(screen.getByText('react-server-dom-webpack')).not.toBeNull();
    expect(screen.getByRole('button', { name: '재검토 목록' })).not.toBeNull();
    expect(screen.queryByRole('button', { name: '조치 후보' })).toBeNull();
  });

  it('shows affected versions in the CVE table and one recommended package version', async () => {
    const litellm = buildDemoRemediationGroups().find((group) => group.package_name === 'litellm');
    render(
      <RemediationPreviewPage
        view="list"
        initialExpandedGroupId={litellm.id}
        onNavigate={vi.fn()}
      />,
    );

    expect(await screen.findByText('영향 버전')).not.toBeNull();
    expect(screen.getByText('>= 1.81.16, < 1.83.7')).not.toBeNull();
    expect(screen.getByText('< 1.83.0')).not.toBeNull();
    const remediationTarget = screen.getByText('조치 대상').closest('section');
    expect(within(remediationTarget).getByText('권장 수정 버전').parentElement.textContent).toContain('1.83.7');
    expect(within(remediationTarget).getByText('현재 사용 버전').parentElement.textContent).toContain('1.81.16');
    expect(screen.queryByText(/GHSA-r75f-5x8p-qvmc/)).toBeNull();
  });

  it('shows declaration and lock files in one dependency project target', async () => {
    window.localStorage.setItem('watchback.dataSource', 'db');
    const django = buildDemoRemediationGroups().find((group) => (
      group.package_name.toLowerCase() === 'django'
    ));
    const mergedTarget = {
      ...django.targets[0],
      project_root: '',
      manifest_path: 'pyproject.toml',
      manifest_paths: ['pyproject.toml', 'uv.lock'],
    };
    const group = { ...django, targets: [mergedTarget] };
    vi.spyOn(remediationGroupData, 'loadRemediationGroups').mockResolvedValue([group]);

    render(
      <RemediationPreviewPage
        view="list"
        initialExpandedGroupId={group.id}
        onNavigate={vi.fn()}
      />,
    );

    const targets = (await screen.findByText('조치 대상')).closest('section');
    expect(within(targets).getByText('의존성 파일').parentElement.textContent)
      .toContain('pyproject.toml · uv.lock');
    expect(within(targets).getAllByRole('button', { name: '조치하기' })).toHaveLength(1);
  });
});
