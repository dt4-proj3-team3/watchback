'use client';

import { Fragment, useEffect, useMemo, useState, useSyncExternalStore } from 'react';
import { useRouter } from 'next/navigation';

import { AiAssistantPreview } from '@/components/original/ai-assistant-preview';
import { Header } from '@/components/original/header';
import { EvidenceCard } from '@/components/original/evidence-card';
import { toReactStyle } from '@/components/original/style';
import * as remediationGroupData from '@/lib/remediation-group-data';
import {
  readStoredDataSource,
  subscribeToDataSource,
} from '@/lib/review-case-data';

const PRIORITY_META = {
  P0: { label: 'Critical', color: '#C7402A', background: '#FBEAE6' },
  P1: { label: 'High', color: '#C7752A', background: '#FCEFE1' },
  P2: { label: 'Medium', color: '#0EA5FF', background: '#E6F3FB' },
  P3: { label: 'Low', color: '#10B981', background: '#E7F3EC' },
};
const CANDIDATE_PRIORITY_ORDER = { P0: 0, P1: 1, P2: 2, P3: 3 };
const CHANGE_LABEL = {
  kev_new: 'KEV 신규 등재',
  kev_added: 'KEV 신규 등재',
  epss_rise_d30: 'EPSS 급등',
  epss_top5_entry_d30: 'EPSS 상위 5% 진입',
  patch_available: '패치 버전 등장',
  combined_signal: '다중 신호 동시 변화',
};
const TIMELINE_CHANGE_LABEL = {
  ...CHANGE_LABEL,
  epss_top5_entry_d30: 'EPSS 상위 5%',
};
const SIGNAL_LABEL = {
  kev: 'CISA KEV 등재',
  epss_score_d30: '향후 30일 악용 가능성',
  epss_percentile_d30: '전체 CVE 내 EPSS 순위',
  patch: '패치 버전',
};
const SCORE_BY_PRIORITY = { P0: 90, P1: 65, P2: 40, P3: 15 };
const SCORE_MARKER = {
  90: { left: 106, top: 36 },
  65: { left: 81, top: 11 },
  40: { left: 46, top: 11 },
  15: { left: 21, top: 36 },
};
const RISK_REASON_LABEL = {
  compatibility_blocked: '호환성 문제로 보류',
  low_current_impact: '현재 영향 낮음',
};
const AI_SUMMARY_EMPHASIS_TERMS = [
  '서버 측 요청 위조',
  '원격 코드 실행',
  'SQL 인젝션',
  'SQL 삽입',
  'SQL 주입',
  '서비스 거부',
  '캐시 중독',
  '파일 접근 제한 우회',
  'CISA KEV',
  'KEV',
  'EPSS',
];
function formatDate(value) {
  if (!value) return '-';
  const date = new Date(value);
  return `${date.getUTCFullYear()}.${String(date.getUTCMonth() + 1).padStart(2, '0')}.${String(date.getUTCDate()).padStart(2, '0')}`;
}

function formatDateTime(value) {
  if (!value) return '-';
  const date = new Date(value);
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Seoul',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(date);
  const part = (type) => parts.find((item) => item.type === type)?.value ?? '';
  return `${part('year')}.${part('month')}.${part('day')} ${part('hour')}:${part('minute')}`;
}

function latestObservedChangeDate(group) {
  const evidenceDates = group.vulnerabilities.flatMap((vulnerability) => (
    (vulnerability.candidates ?? []).flatMap((candidate) => (
      (candidate.evidence ?? []).map((evidence) => evidence.observed_at).filter(Boolean)
    ))
  ));
  const annotationDates = group.vulnerabilities.flatMap((vulnerability) => (
    (vulnerability.candidates ?? []).flatMap((candidate) => (
      (candidate.deliveries ?? []).flatMap((delivery) => (
        (delivery.source_annotations ?? []).map((annotation) => annotation.snapshot_date).filter(Boolean)
      ))
    ))
  ));
  const sourceDates = evidenceDates.length > 0 ? evidenceDates : annotationDates;
  return sourceDates.sort((left, right) => new Date(right) - new Date(left))[0] ?? null;
}

function formatRecentChangeDate(value) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  const monthAndDay = `${String(date.getUTCMonth() + 1).padStart(2, '0')}.${String(date.getUTCDate()).padStart(2, '0')}`;
  return date.getUTCFullYear() === new Date().getUTCFullYear()
    ? monthAndDay
    : `${date.getUTCFullYear()}.${monthAndDay}`;
}

function historyLabel(item, totalTargetCount) {
  const scope = item.target_count >= totalTargetCount ? '전체' : '개별';
  if (item.event_type === 'risk_acceptance_revoked') return `재검토 열기 · ${scope}`;
  if (item.event_type === 'remediation_requested') {
    if (item.watchback_state === 'completed') return `조치 완료 · ${scope}`;
    if (item.watchback_state === 'pr_merged') return `PR 병합 · ${scope}`;
    if (item.watchback_state === 'pr_open') return `PR 생성 · ${scope}`;
    return `조치 요청 · ${scope}`;
  }
  return `위험 수용 · ${scope}`;
}

function historyDetail(item) {
  if (item.event_type === 'remediation_requested') {
    const targetVersions = [...new Set(
      (item.pull_requests ?? []).map((pullRequest) => pullRequest.target_version).filter(Boolean),
    )];
    if (targetVersions.length > 0) return `${targetVersions.join(', ')} 업데이트`;
    return item.note;
  }
  if (item.event_type !== 'risk_accepted') return item.note;
  return RISK_REASON_LABEL[item.reason_code] ?? item.note ?? '기타';
}

function targetPullRequests(group, target) {
  const uniqueByUrl = new Map();
  for (const item of group.action_history ?? []) {
    for (const pullRequest of item.pull_requests ?? []) {
      if (pullRequest.closed) continue;
      if (
        pullRequest.repository_full_name === target.repository.full_name
        && (pullRequest.project_root ?? '') === (target.project_root ?? '')
      ) {
        uniqueByUrl.set(pullRequest.url, pullRequest);
      }
    }
  }
  return [...uniqueByUrl.values()];
}

function existingOpenPullRequestBatch(group) {
  const action = (group.action_history ?? []).find((item) => (
    item.event_type === 'remediation_requested'
    && item.watchback_state === 'pr_open'
    && (item.pull_requests ?? []).some((pullRequest) => !pullRequest.merged && !pullRequest.closed)
  ));
  if (!action) return null;
  return {
    id: action.id,
    pull_requests: action.pull_requests.filter((pullRequest) => !pullRequest.merged && !pullRequest.closed),
  };
}

function ActionHistoryRow({ item, totalTargetCount, isLatest, isLast }) {
  return <div style={toReactStyle('position:relative;padding:0 0 18px 25px;min-width:0')}>
    {!isLast && <span aria-hidden="true" style={toReactStyle('position:absolute;left:5px;top:12px;bottom:-2px;width:1px;background:#DDE2DC')} />}
    <span aria-hidden="true" style={toReactStyle(`position:absolute;left:0;top:4px;width:11px;height:11px;box-sizing:border-box;border:2px solid ${isLatest ? '#2F8F5B' : '#C5CAC3'};border-radius:50%;background:${isLatest ? '#2F8F5B' : '#FFFFFF'};box-shadow:0 0 0 3px #FFFFFF`)} />
    <strong style={toReactStyle('display:block;font-size:11.5px;line-height:18px;color:#1B1E1A')}>{historyLabel(item, totalTargetCount)}</strong>
    {historyDetail(item) && <span style={toReactStyle('display:block;font-size:10.5px;line-height:17px;color:#737A71;margin-top:2px')}>{historyDetail(item)}</span>}
    <span style={toReactStyle('display:block;font-size:9.5px;line-height:15px;color:#9A9F97;margin-top:4px')}>{formatDateTime(item.occurred_at)} · {item.actor_display_name}</span>
  </div>;
}

function formatCurrentVersions(target) {
  if (target.current_version_status === 'multiple' && target.current_versions?.length) {
    return target.current_versions.join(', ');
  }
  return target.current_version ?? '확인 불가';
}

function formatDependencyFiles(target) {
  const paths = target.manifest_paths?.length
    ? target.manifest_paths
    : target.manifest_path ? [target.manifest_path] : [];
  return paths.length ? paths.join(' · ') : '확인 불가';
}

function formatEvidenceValue(value, evidence) {
  if (value == null || value === '') return '-';
  if (evidence.signal === 'kev') return value === 'true' ? '등재' : '미등재';
  const number = Number(value);
  if (evidence.value_type !== 'decimal' || !Number.isFinite(number)) return value;
  if (evidence.signal === 'epss_percentile_d30') {
    return `상위 ${((1 - number) * 100).toFixed(1).replace(/\.0$/, '')}%`;
  }
  if (evidence.signal === 'epss_score_d30') {
    const percent = number * 100;
    return `${percent.toFixed(percent > 0 && percent < 0.1 ? 2 : 1).replace(/\.0+$/, '')}%`;
  }
  return value;
}

function formatEvidenceDescription(evidence) {
  if (evidence.signal === 'kev' && evidence.previous_value === 'false' && evidence.current_value === 'true') {
    return 'CISA에서 실제 악용 사례가 확인되었습니다.';
  }
  if (evidence.signal === 'epss_score_d30') {
    const previous = Number(evidence.previous_value);
    const current = Number(evidence.current_value);
    if (Number.isFinite(previous) && Number.isFinite(current)) {
      const delta = (current - previous) * 100;
      return `30일 전보다 ${delta.toFixed(1).replace(/\.0$/, '')}%p 상승했습니다.`;
    }
  }
  if (evidence.signal === 'epss_percentile_d30') {
    const previous = Number(evidence.previous_value);
    const percentile = Number(evidence.current_value);
    if (Number.isFinite(percentile)) {
      if (Number.isFinite(previous) && previous < 0.95 && percentile >= 0.95) {
        return '상위 5% 구간에 진입했습니다.';
      }
      return `전체 CVE 중 상위 ${((1 - percentile) * 100).toFixed(1).replace(/\.0$/, '')}%에 해당합니다.`;
    }
  }
  return evidence.evidence_summary;
}

function badge(priority) {
  const meta = PRIORITY_META[priority] ?? PRIORITY_META.P3;
  return {
    label: meta.label,
    style: `font-size:12px;font-weight:700;color:${meta.color};background:${meta.background};border-radius:16px;padding:3px 9px`,
  };
}

function packageChangeTags(group) {
  const candidates = group.vulnerabilities.flatMap((item) => item.candidates ?? []);
  const evidence = candidates.flatMap((candidate) => candidate.evidence ?? []);
  const changeTypes = new Set(candidates.map((candidate) => candidate.change_type));
  const hasKev = changeTypes.has('kev_new') || changeTypes.has('kev_added') || evidence.some((item) => (
    item.signal === 'kev' && item.current_value === 'true'
  ));
  const hasEpssRise = changeTypes.has('epss_rise_d30') || evidence.some((item) => (
    item.signal === 'epss_score_d30' && Number(item.current_value) > Number(item.previous_value)
  ));
  const hasTopFive = changeTypes.has('epss_top5_entry_d30') || evidence.some((item) => (
    item.signal === 'epss_percentile_d30' &&
    Number(item.previous_value) < 0.95 &&
    Number(item.current_value) >= 0.95
  ));

  return [
    hasKev && { label: 'NEW KEV', style: 'color:#A6321B;background:#FBEAE6;border:1px solid #FFCABD' },
    hasEpssRise && { label: 'EPSS 급등', style: 'color:#2F8F5B;background:#E7F3EC;border:1px solid #BFEBD7' },
    hasTopFive && { label: 'EPSS 상위 5%', style: 'color:#1F6FBF;background:#E6EFFA;border:1px solid #C5D8F0' },
  ].filter(Boolean).slice(0, 1);
}

function primaryVulnerabilityType(group) {
  const summary = group.vulnerabilities?.[0]?.advisory?.summary?.toLowerCase() ?? '';
  const types = [
    [/(?:sql injection|sql 인젝션)/, 'SQLi'],
    [/(?:remote code execution|arbitrary command execution|execute commands on the local system|\brce\b)/, 'RCE'],
    [/(?:server-side request forgery|\bssrf\b)/, 'SSRF'],
    [/(?:denial[- ]of[- ]service|\bdos\b)/, 'DoS'],
    [/(?:cross-site scripting|\bxss\b)/, 'XSS'],
    [/(?:authorization bypass|authentication bypass)/, '인증 우회'],
    [/(?:privilege escalation)/, '권한 상승'],
    [/(?:arbitrary file read|file read|server\.fs\.deny)/, 'File Read'],
    [/(?:cache poisoning)/, '캐시 오염'],
    [/(?:path traversal)/, '경로 탐색'],
  ];
  return types.find(([pattern]) => pattern.test(summary))?.[1] ?? '-';
}

function pageNav(router, navigate, activeView) {
  const go = navigate ?? ((path) => router.push(path));
  return [
    { key: 'dashboard', label: '대시보드', path: '/dashboard' },
    { key: 'list', label: '재검토 목록', path: '/review-cases' },
    { key: 'repos', label: '저장소', path: '/repositories' },
  ].map((item) => ({
    ...item,
    onClick: () => go(item.path),
    style: `font-size:13px;font-weight:600;padding:8px 12px;border-radius:7px;cursor:pointer;color:${item.key === activeView ? '#1B1E1A' : '#8B9086'};background:${item.key === activeView ? '#EEF0EE' : 'transparent'}`,
  }));
}

/**
 * @param {{
 *   view: 'dashboard' | 'list',
 *   initialExpandedGroupId?: string | null,
 *   initialRepositoryFullName?: string | null,
 *   onNavigate?: ((path: string) => void) | null,
 *   onBack?: (() => void) | null,
 * }} props
 */
export function RemediationPreviewPage({
  view,
  initialExpandedGroupId = null,
  initialRepositoryFullName = null,
  onNavigate = null,
  onBack = null,
  apiFetcher = globalThis.fetch,
}) {
  const router = useRouter();
  const dataSource = useSyncExternalStore(
    subscribeToDataSource,
    () => readStoredDataSource(window.localStorage),
    () => 'db',
  );
  const [groups, setGroups] = useState([]);
  const [loadState, setLoadState] = useState('loading');
  const [loadError, setLoadError] = useState('');
  const [retryKey, setRetryKey] = useState(0);
  const summary = useMemo(
    () => remediationGroupData.summarizeRemediationGroups(groups, dataSource),
    [dataSource, groups],
  );
  const [filters, setFilters] = useState({
    status: 'all',
    priority: 'all',
    changeType: 'all',
    importance: 'all',
    repository: initialRepositoryFullName ?? 'all',
    sort: 'recent_change',
  });
  const navigate = onNavigate ?? ((path) => router.push(path));
  const backToPrevious = onBack ?? (() => router.back());
  const filteredGroups = groups.filter((group) => (
    (filters.status === 'all' || group.status === filters.status) &&
    (filters.priority === 'all' || group.priority === filters.priority) &&
    (filters.changeType === 'all' || group.vulnerabilities.some((vulnerability) => (
      vulnerability.candidates?.some((candidate) => (
        candidate.change_type === filters.changeType ||
        (filters.changeType === 'kev_new' && candidate.change_type === 'kev_added')
      ))
    ))) &&
    (filters.importance === 'all' || group.targets.some((target) => (
      (target.repository.importance === 'critical' ? 'high' : target.repository.importance) === filters.importance
    ))) &&
    (filters.repository === 'all' || group.targets.some((target) => (
      target.repository.full_name === filters.repository
    )))
  )).sort((left, right) => {
    if (filters.sort === 'priority') {
      return (
        (CANDIDATE_PRIORITY_ORDER[left.priority] ?? 99) -
          (CANDIDATE_PRIORITY_ORDER[right.priority] ?? 99) ||
        new Date(latestObservedChangeDate(right) ?? 0) -
          new Date(latestObservedChangeDate(left) ?? 0)
      );
    }
    const dateOf = filters.sort === 'registered'
      ? (group) => group.registered_at
      : latestObservedChangeDate;
    return new Date(dateOf(right) ?? 0) - new Date(dateOf(left) ?? 0);
  });
  const focusedGroups = initialExpandedGroupId
    ? filteredGroups.filter((group) => group.id === initialExpandedGroupId)
    : filteredGroups;
  const focusedGroup = focusedGroups[0] ?? null;
  const activeRepositoryLabel = filters.repository === 'all'
    ? null
    : groups.flatMap((group) => group.targets)
      .find((target) => target.repository.full_name === filters.repository)
      ?.repository.display_name ?? filters.repository;

  useEffect(() => {
    let cancelled = false;
    remediationGroupData.loadRemediationGroups(dataSource)
      .then((nextGroups) => {
        if (cancelled) return;
        setGroups(nextGroups);
        setLoadState('ready');
      })
      .catch((error) => {
        if (cancelled) return;
        setGroups([]);
        setLoadError(error instanceof Error ? error.message : '패키지 조치 후보를 불러오지 못했습니다.');
        setLoadState('error');
      });
    return () => { cancelled = true; };
  }, [dataSource, retryKey]);

  const headerValues = {
    goToDashboard: () => navigate('/dashboard'),
    navTabs: pageNav(router, navigate, view === 'dashboard' ? 'dashboard' : 'list'),
    isPreview: false,
    dataSource,
  };

  return (
    <div style={{ minHeight: '100vh', background: '#FAFBFA', fontFamily: "'Noto Sans KR',-apple-system,'Segoe UI',Helvetica,Arial,sans-serif", color: '#1B1E1A' }}>
      <Header values={headerValues} />
      {loadState === 'loading'
        ? <RemediationLoadState message="패키지 조치 후보를 불러오는 중입니다." />
        : loadState === 'error'
        ? <RemediationLoadState message={loadError} actionLabel="다시 시도" onAction={() => { setLoadState('loading'); setLoadError(''); setRetryKey((value) => value + 1); }} />
        : view === 'dashboard'
        ? <RemediationDashboard
            groups={groups}
            summary={summary}
            onOpen={(groupId) => navigate(`/review-cases/${encodeURIComponent(groupId)}`)}
            onOpenAll={() => navigate('/review-cases')}
          />
        : <RemediationList
            groups={focusedGroups}
            filters={filters}
            setFilters={setFilters}
            activeRepositoryLabel={activeRepositoryLabel}
            focused={!!initialExpandedGroupId}
            onBack={backToPrevious}
            onOpenGroup={(groupId) => navigate(`/review-cases/${encodeURIComponent(groupId)}`)}
            dataSource={dataSource}
            apiFetcher={apiFetcher}
            onRefresh={() => {
              setLoadState('loading');
              setRetryKey((value) => value + 1);
            }}
          />}
      <AiAssistantPreview values={{
        selected: focusedGroup
          ? {
              advisory: { cve_id: focusedGroup.package_name },
              affectedRepositoryLabel: `저장소 ${focusedGroup.repository_count}곳 · CVE ${focusedGroup.cve_count}건`,
              remediationGroupId: focusedGroup.id,
            }
          : null,
        isDashboardView: view === 'dashboard',
        isListView: view === 'list',
        resultCountLabel: `${filteredGroups.length}건`,
        dataSource,
      }} />
    </div>
  );
}

function RemediationLoadState({ message, actionLabel = null, onAction = null }) {
  return <main className="watchback-page" style={toReactStyle('width:calc(100% - 64px);max-width:1120px;margin:0 auto;padding:96px 0;text-align:center')}>
    <p role="status" style={toReactStyle('font-size:13px;color:#737A71;margin:0 0 14px')}>{message}</p>
    {actionLabel && <button type="button" onClick={onAction} style={toReactStyle('font-family:inherit;font-size:12px;line-height:18px;font-weight:700;color:#FFFFFF;background:#2F8F5B;border:0;border-radius:7px;padding:8px 14px;cursor:pointer')}>{actionLabel}</button>}
  </main>;
}

function PreviewHeading({ title }) {
  return <div style={toReactStyle('display:flex;align-items:flex-start;justify-content:space-between;gap:24px;margin-bottom:28px')}>
    <div>
      <div style={toReactStyle('display:flex;align-items:center;gap:10px;margin-bottom:7px')}><h1 style={toReactStyle('font-size:25px;line-height:36px;font-weight:700;margin:0')}>{title}</h1></div>
    </div>
  </div>;
}

function RemediationDashboard({ groups, summary, onOpen, onOpenAll }) {
  const severityColors = { P0: '#FF4D4F', P1: '#F59E0B', P2: '#0EA5FF', P3: '#10B981' };
  const openGroups = groups.filter((group) => group.status === 'open');
  const severitySummary = ['P0', 'P1', 'P2', 'P3'].map((priority) => {
    const count = openGroups.filter((group) => group.priority === priority).length;
    return { priority, count, color: severityColors[priority] };
  });
  const kevGroupCount = openGroups.filter((group) => (
    packageChangeTags(group).some((tag) => tag.label === 'NEW KEV')
  )).length;
  const statusCards = [['KEV 포함', kevGroupCount], ['위험 수용', summary.accepted], ['해결됨', summary.resolved]];
  const priorityQueue = openGroups.slice(0, 5);

  return <main className="watchback-page watchback-remediation-page" style={toReactStyle('width:calc(100% - 64px);max-width:1120px;margin:0 auto;padding:46px 0 96px')}>
    <PreviewHeading title="Review Summary" />
    <section className="watchback-summary-grid watchback-remediation-summary" style={toReactStyle('display:grid;grid-template-columns:360px repeat(3,minmax(0,1fr));gap:14px;margin-bottom:42px')}>
      <div style={toReactStyle('height:110px;box-sizing:border-box;background:#FFFFFF;border:1px solid #E2E8F0;border-radius:9px;padding:23px')}>
        <div style={toReactStyle('display:flex;gap:2px;height:11px;border-radius:6px;overflow:hidden;margin-bottom:16px')}>
          {severitySummary.filter((item) => item.count > 0).map((item) => <span key={item.priority} style={{ flex: `${item.count} 1 0`, minWidth: 0, background: item.color }} />)}
        </div>
        <div style={toReactStyle('display:flex;align-items:center;gap:6px')}>
          <strong style={toReactStyle('font:500 30px/38px Inter,Arial,sans-serif;color:#0F172A')}>{summary.open}</strong>
          <span style={toReactStyle('font:400 18px/24px Inter,Arial,sans-serif;color:#0F172A;margin-right:auto')}>Issues</span>
          {severitySummary.map((item) => <Fragment key={item.priority}><span style={toReactStyle(`width:8px;height:8px;border-radius:1px;background:${item.color}`)} /><span style={toReactStyle('font:500 12px/18px Inter,Arial,sans-serif;color:#0F172A')}>{item.count}</span></Fragment>)}
        </div>
      </div>
      {statusCards.map(([label, count]) => <div key={label} style={toReactStyle('height:110px;box-sizing:border-box;background:#FFFFFF;border:1px solid #E3E7E1;border-radius:9px;padding:19px 21px')}>
        <span style={toReactStyle('display:block;font-size:12px;color:#7C8379;margin-bottom:10px')}>{label}</span>
        <strong style={toReactStyle('font:500 30px/38px Inter,Arial,sans-serif;color:#0F172A')}>{count}</strong>
      </div>)}
    </section>
    <div style={toReactStyle('display:flex;align-items:center;justify-content:space-between;margin-bottom:23px')}>
      <h2 style={toReactStyle('font-size:25px;line-height:36px;font-weight:700;margin:0')}>Priority Queue</h2>
      <button type="button" onClick={onOpenAll} style={toReactStyle('font-size:13px;line-height:19px;font-weight:700;color:#6B7280;background:none;border:0;padding:0;cursor:pointer')}>전체 보기 →</button>
    </div>
    <PackageColumns />
    <div data-testid="remediation-priority-queue" style={toReactStyle('display:flex;flex-direction:column;gap:12px;margin-top:16px')}>
      {priorityQueue.map((group) => <PackageRow key={group.id} group={group} onClick={() => onOpen(group.id)} />)}
    </div>
  </main>;
}

function RemediationList({
  groups,
  filters,
  setFilters,
  activeRepositoryLabel,
  focused,
  onBack,
  onOpenGroup,
  dataSource,
  apiFetcher,
  onRefresh,
}) {
  if (focused && groups[0]) {
    return <RemediationFocusedDetail group={groups[0]} onBack={onBack} dataSource={dataSource} apiFetcher={apiFetcher} onRefresh={onRefresh} />;
  }

  return <main className="watchback-page watchback-remediation-page" style={toReactStyle('width:calc(100% - 64px);max-width:1120px;margin:0 auto;padding:46px 0 96px')}>
    <PreviewHeading title={focused ? '패키지 조치 상세' : '재검토 목록'} />
    {!focused && <div className="watchback-remediation-filters" style={toReactStyle('display:flex;flex-direction:column;gap:26px;margin-bottom:34px')}>
      <div style={toReactStyle('display:grid;grid-template-columns:minmax(380px,.9fr) minmax(560px,1.4fr);gap:28px 42px;align-items:start')}>
        <Filter label="정렬" values={['priority', 'recent_change', 'registered']} active={filters.sort} labels={{ priority: '우선순위 순', recent_change: '최근 업데이트 순', registered: '생성일 순' }} onChange={(sort) => setFilters({ ...filters, sort })} />
        <Filter label="상태" values={['all', 'open', 'accepted', 'resolved']} active={filters.status} labels={{ all: '전체', open: '열림', accepted: '위험 수용', resolved: '해결됨' }} onChange={(status) => setFilters({ ...filters, status })} />
        <Filter label="우선순위" values={['all', 'P0', 'P1', 'P2', 'P3']} active={filters.priority} labels={{ all: '전체', P0: 'Critical', P1: 'High', P2: 'Medium', P3: 'Low' }} onChange={(priority) => setFilters({ ...filters, priority })} />
        <Filter label="저장소 중요도" values={['all', 'high', 'medium', 'low']} active={filters.importance} labels={{ all: '전체', high: 'High', medium: 'Medium', low: 'Low' }} onChange={(importance) => setFilters({ ...filters, importance })} />
        <Filter label="변화 유형" values={['all', 'kev_new', 'epss_rise_d30', 'epss_top5_entry_d30']} active={filters.changeType} labels={{ all: '전체', kev_new: 'KEV 신규 등재', epss_rise_d30: 'EPSS 급등', epss_top5_entry_d30: 'EPSS 상위 5% 진입' }} onChange={(changeType) => setFilters({ ...filters, changeType })} />
      </div>
    </div>}
    {!focused && activeRepositoryLabel && <div style={toReactStyle('margin:0 0 20px')}>
      <button type="button" onClick={() => setFilters({ ...filters, repository: 'all' })} style={toReactStyle('font:600 13px/19px inherit;color:#1B1E1A;background:#EEF0EE;border:1px solid #D2D5CD;border-radius:18px;padding:7px 12px;cursor:pointer')}>저장소: {activeRepositoryLabel} ×</button>
    </div>}
    {focused && <div style={toReactStyle('font-size:13px;color:#737A71;margin-bottom:14px')}>선택한 패키지 조치 범위</div>}
    <PackageColumns />
    {groups.length === 0 && <div style={toReactStyle('background:#FFFFFF;border:1px solid #E3E7E1;border-radius:9px;padding:64px 24px;text-align:center;color:#8B9086;margin-top:16px')}>현재 조건에 맞는 조치 후보가 없습니다.</div>}
    <div style={toReactStyle('display:flex;flex-direction:column;gap:10px;margin-top:16px')}>
      {groups.map((group) => <div key={group.id}>
        <PackageRow
          group={group}
          onClick={() => onOpenGroup(group.id)}
        />
      </div>)}
    </div>
  </main>;
}

function Filter({ label, values, active, labels, onChange }) {
  return <div>
    <strong style={toReactStyle('display:block;font-size:14px;line-height:21px;font-weight:700;color:#737A71;margin-bottom:12px')}>{label}</strong>
    <FilterButtons gap={10} values={values} active={active} labels={labels} onChange={onChange} />
  </div>;
}

function FilterButtons({ values, active, labels, onChange, gap }) {
  return <div style={toReactStyle(`display:flex;align-items:center;gap:${gap}px;flex-wrap:wrap`)}>
    {values.map((value) => <button key={value} type="button" aria-pressed={active === value} onClick={() => onChange(value)} style={toReactStyle(`font-family:inherit;font-size:13px;line-height:19px;font-weight:600;color:${active === value ? '#1B1E1A' : '#8B9086'};background:${active === value ? '#EEF0EE' : '#FFFFFF'};border:1px solid ${active === value ? '#D2D5CD' : '#E4E6E1'};border-radius:7px;padding:7px 12px;cursor:pointer`)}>{labels[value]}</button>)}
  </div>;
}

function PackageColumns() {
  return <div className="watchback-remediation-columns" style={toReactStyle('display:grid;grid-template-columns:90px 220px 105px 60px 170px 120px minmax(105px,1fr) 16px;gap:16px;padding:0 14px 12px 22px;font:700 13px/19px Inter,Arial,sans-serif;color:#6B7280;border-bottom:1px solid #E3E7E1')}>
    <span>우선순위</span><span>패키지</span><span>핵심 취약점</span><span>CVE</span><span>저장소 · Open Alert</span><span>변화</span><span>권장 수정 버전</span><span aria-hidden="true" />
  </div>;
}

function PackageRow({ group, onClick, expanded = false }) {
  const priority = badge(group.priority);
  const changeTags = packageChangeTags(group);
  const recentChangeDate = formatRecentChangeDate(latestObservedChangeDate(group));
  return <button type="button" aria-expanded={expanded} onClick={onClick} className="watchback-remediation-row" style={toReactStyle(`width:100%;display:grid;grid-template-columns:90px 220px 105px 60px 170px 120px minmax(105px,1fr) 16px;align-items:center;gap:16px;min-height:76px;text-align:left;font-family:inherit;color:#1B1E1A;background:linear-gradient(90deg,${PRIORITY_META[group.priority].color} 0 3px,#FFFFFF 3px);border:1px solid #E3E7E1;border-radius:9px;padding:10px 14px 10px 22px;cursor:pointer`)}>
    <span><b style={toReactStyle(priority.style)}>{priority.label}</b></span>
    <span><strong title={group.package_name} style={toReactStyle('display:block;font-size:13px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap')}>{group.package_name}</strong><small style={toReactStyle('font-size:11px;color:#8B9086')}>{group.ecosystem}</small></span>
    <span style={toReactStyle('font-size:12px;font-weight:500;color:#3F443D;white-space:nowrap')}>{primaryVulnerabilityType(group)}</span>
    <span style={toReactStyle('font-size:12px;color:#515250')}>{group.cve_count}건</span>
    <span style={toReactStyle('font-size:12px;color:#515250')}>{group.repository_count}곳 · {group.open_alert_count}건</span>
    <span style={toReactStyle('display:flex;flex-direction:column;align-items:flex-start;gap:4px')}><span style={toReactStyle('display:flex;align-items:center;gap:4px;flex-wrap:wrap')}>{changeTags.map((tag) => <b key={tag.label} style={toReactStyle(`font-size:9px;font-weight:600;border-radius:12px;padding:3px 8px;white-space:nowrap;${tag.style}`)}>{tag.label}</b>)}</span>{recentChangeDate && <small style={toReactStyle('font-size:9.5px;line-height:14px;color:#9A9F97;white-space:nowrap')}>최근 변화 {recentChangeDate}</small>}</span>
    <span><strong style={toReactStyle('display:block;font-size:12px;color:#2F8F5B')}>{group.representative_patched_version ?? '없음'}</strong></span>
    <span aria-hidden="true" style={toReactStyle(`color:#CBD5E1;font-size:18px;transform:rotate(${expanded ? '90deg' : '0deg'})`)}>›</span>
  </button>;
}

function RemediationFocusedDetail({ group, onBack, dataSource, apiFetcher, onRefresh }) {
  const [expandedCve, setExpandedCve] = useState(null);
  const [expandedAlertTarget, setExpandedAlertTarget] = useState(null);
  const [actionScope, setActionScope] = useState(null);
  const [actionNotice, setActionNotice] = useState('');
  const [actionNote, setActionNote] = useState('');
  const [riskReason, setRiskReason] = useState('');
  const [actionSubmitting, setActionSubmitting] = useState(false);
  const [pullRequestPhase, setPullRequestPhase] = useState('ready');
  const [pullRequestBatch, setPullRequestBatch] = useState(null);
  const score = SCORE_BY_PRIORITY[group.priority] ?? 15;
  const marker = SCORE_MARKER[score];
  const priority = badge(group.priority);
  const isRiskScope = actionScope === 'risk' || actionScope?.startsWith('risk:');
  const isReopenScope = actionScope === 'reopen' || actionScope?.startsWith('reopen:');
  const scopedTargetId = actionScope?.includes(':') ? actionScope.split(':')[1] : null;
  const selectedTarget = group.targets.find((target) => (
    target.id === (scopedTargetId ?? actionScope)
  ));
  const isPullRequestScope = actionScope === 'all' || (
    selectedTarget && !isRiskScope && !isReopenScope
  );
  const actionableTargets = group.targets.filter((target) => target.open_alert_count > 0);
  const pullRequestTargets = selectedTarget ? [selectedTarget] : actionableTargets;
  const actionableRepositoryCount = new Set(pullRequestTargets.map((target) => target.repository.id)).size;
  const openAllActionModal = () => {
    const existingBatch = existingOpenPullRequestBatch(group);
    setActionScope('all');
    setActionNotice('');
    setPullRequestBatch(existingBatch);
    setPullRequestPhase(existingBatch ? 'created' : 'ready');
  };
  const closeActionModal = () => {
    const shouldRefresh = ['completed', 'verification_pending', 'closed'].includes(pullRequestPhase);
    setActionScope(null);
    setActionNotice('');
    setActionNote('');
    setRiskReason('');
    setPullRequestPhase('ready');
    setPullRequestBatch(null);
    if (shouldRefresh) onRefresh?.();
  };
  const submitGroupAction = async (actionType, noteValue = null, reasonCode = null) => {
    const note = noteValue?.trim() || null;
    if (actionSubmitting) return;
    if (dataSource === 'demo') {
      setActionNotice('Demo 데이터에서는 조치 기록을 저장하지 않습니다.');
      return;
    }
    setActionSubmitting(true);
    setActionNotice('');
    try {
      const result = await remediationGroupData.createRemediationAction(dataSource, group.id, {
        action_type: actionType,
        target_ids: scopedTargetId ? [scopedTargetId] : null,
        reason_code: reasonCode,
        note,
      });
      setActionNotice(`${result.targets.length}개 Open Alert 대상에 조치를 기록했습니다.`);
      setActionNote('');
      setActionScope(null);
      onRefresh?.();
    } catch (error) {
      setActionNotice(error instanceof Error ? error.message : '조치를 기록하지 못했습니다.');
    } finally {
      setActionSubmitting(false);
    }
  };
  const reopenGroup = async () => {
    if (actionSubmitting) return;
    if (dataSource === 'demo') {
      setActionNotice('Demo 데이터에서는 재검토 상태를 변경하지 않습니다.');
      return;
    }
    setActionSubmitting(true);
    setActionNotice('');
    try {
      await remediationGroupData.reopenRemediationGroup(
        dataSource,
        group.id,
        scopedTargetId ? [scopedTargetId] : null,
      );
      setActionScope(null);
      onRefresh?.();
    } catch (error) {
      setActionNotice(error instanceof Error ? error.message : '재검토를 열지 못했습니다.');
    } finally {
      setActionSubmitting(false);
    }
  };
  const createPullRequests = async () => {
    if (actionSubmitting) return;
    if (dataSource === 'demo') {
      setActionNotice('Demo 데이터에서는 업데이트 PR을 생성하지 않습니다.');
      return;
    }
    setActionSubmitting(true);
    setPullRequestPhase('creating');
    setActionNotice('');
    try {
      const result = await remediationGroupData.createRemediationPullRequests(
        dataSource,
        group.id,
        selectedTarget ? [selectedTarget.id] : null,
        apiFetcher,
      );
      setPullRequestBatch(result);
      setPullRequestPhase('created');
    } catch (error) {
      setPullRequestPhase('ready');
      setActionNotice(error instanceof Error ? error.message : '업데이트 PR을 생성하지 못했습니다.');
    } finally {
      setActionSubmitting(false);
    }
  };
  const mergePullRequests = async () => {
    if (actionSubmitting || !pullRequestBatch?.id) return;
    setActionSubmitting(true);
    setPullRequestPhase('merging');
    setActionNotice('');
    try {
      const result = await remediationGroupData.mergeRemediationPullRequests(
        dataSource,
        group.id,
        pullRequestBatch.id,
        apiFetcher,
      );
      setPullRequestBatch((current) => ({ ...current, ...result }));
      setPullRequestPhase(
        result.watchback_state === 'completed' ? 'completed' : 'verification_pending',
      );
    } catch (error) {
      setPullRequestPhase('created');
      setActionNotice(error instanceof Error ? error.message : '업데이트 PR을 병합하지 못했습니다.');
    } finally {
      setActionSubmitting(false);
    }
  };
  const closePullRequests = async () => {
    if (actionSubmitting || !pullRequestBatch?.id) return;
    setActionSubmitting(true);
    setPullRequestPhase('closing');
    setActionNotice('');
    try {
      const result = await remediationGroupData.closeRemediationPullRequests(
        dataSource,
        group.id,
        pullRequestBatch.id,
        apiFetcher,
      );
      setPullRequestBatch((current) => ({ ...current, ...result }));
      setPullRequestPhase('closed');
    } catch (error) {
      setPullRequestPhase('created');
      setActionNotice(error instanceof Error ? error.message : '업데이트 PR을 닫지 못했습니다.');
    } finally {
      setActionSubmitting(false);
    }
  };

  return <main data-testid={`remediation-detail-${group.package_name}`} className="watchback-page" style={toReactStyle('width:calc(100% - 64px);max-width:1120px;margin:0 auto;padding:34px 0 96px')}>
    <button type="button" aria-label="이전 화면으로" onClick={onBack} style={toReactStyle('display:flex;align-items:center;font:18px/20px inherit;color:#5B6058;cursor:pointer;margin-bottom:20px;width:fit-content;background:none;border:none;padding:0')}>←</button>
    <div className="watchback-case-summary" style={toReactStyle('position:relative;height:176px;background:#FFFFFF;border:1px solid #E4E6E1;border-radius:9px;margin-bottom:16px;overflow:hidden')}>
      <div aria-label={`조치 우선순위 점수 ${score}점`} style={toReactStyle('position:absolute;left:22px;top:22px;width:132px;height:71px;text-align:center')}>
        <div style={toReactStyle("position:relative;width:132px;height:70px;background:url('/watchback-meter-base.svg') center top/132px 66px no-repeat")}>
          <strong style={toReactStyle('position:absolute;left:0;right:0;bottom:5px;font:500 22px/23px Inter,Arial,sans-serif;color:#515050')}>{score}</strong>
          <span aria-hidden="true" style={toReactStyle(`position:absolute;left:${marker.left}px;top:${marker.top}px;width:5px;height:5px;background:url('/watchback-meter-dot.svg') center/5px 5px no-repeat`)} />
        </div>
      </div>
      <div style={toReactStyle('position:absolute;left:179px;top:29px;width:450px;display:flex;align-items:center;gap:9px')}><strong style={toReactStyle('font:700 20px/28px Inter,Arial,sans-serif')}>{group.package_name} · {group.ecosystem}</strong><span style={toReactStyle(priority.style)}>{priority.label}</span>{group.status !== 'open' && <span style={toReactStyle(`flex-shrink:0;white-space:nowrap;margin-left:7px;font-size:12px;font-weight:700;border-radius:16px;padding:3px 9px;color:${group.status === 'accepted' ? '#5B6058' : '#2F8F5B'};background:${group.status === 'accepted' ? '#EEF0EE' : '#E7F3EC'}`)}>{group.status === 'accepted' ? '위험 수용' : '해결됨'}</span>}</div>
      {group.registered_at && <span style={toReactStyle('position:absolute;left:179px;top:64px;font-size:10.5px;line-height:16px;color:#8B9086')}>검토 대상 등록 {formatDate(group.registered_at)}</span>}
      <SummaryMetric left="33px" label="CVE" value={`${group.cve_count}건`} />
      <SummaryMetric left="105px" label="Open Alert" value={`${group.open_alert_count}건`} />
      <SummaryMetric left="205px" label="저장소" value={`${group.repository_count}곳`} />
      <SummaryMetric left="315px" label="권장 수정 버전" value={group.representative_patched_version ?? '없음'} color="#2F8F5B" emphasis />
      <div style={toReactStyle('position:absolute;right:14px;top:22px;display:flex;gap:8px')}>
        {group.status === 'open' && <button type="button" onClick={() => { setActionScope('risk'); setActionNotice(''); setActionNote(''); setRiskReason(''); }} style={toReactStyle('font-size:12.5px;font-weight:700;font-family:inherit;color:#5B6058;background:#FFFFFF;border:1px solid #D2D5CD;border-radius:7px;padding:8px 14px;cursor:pointer')}>전체 위험 수용</button>}
        {group.status === 'accepted' && <button type="button" disabled={actionSubmitting} onClick={() => { setActionScope('reopen'); setActionNotice(''); }} style={toReactStyle('font-size:12.5px;font-weight:700;font-family:inherit;color:#5B6058;background:#FFFFFF;border:1px solid #D2D5CD;border-radius:7px;padding:8px 14px;cursor:pointer')}>전체 재검토 열기</button>}
        {group.status !== 'resolved' && <button type="button" onClick={openAllActionModal} style={toReactStyle('font-size:12.5px;font-weight:700;font-family:inherit;color:#FFFFFF;background:#2F8F5B;border:none;border-radius:7px;padding:8px 14px;cursor:pointer')}>전체 조치</button>}
      </div>
    </div>
    {actionScope && <div role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) closeActionModal(); }} style={toReactStyle('position:fixed;inset:0;z-index:60;display:flex;align-items:center;justify-content:center;background:rgba(27,30,26,.36);padding:24px')}>
      <section role="dialog" aria-modal="true" aria-labelledby="remediation-action-title" style={toReactStyle('width:min(720px,100%);max-height:calc(100vh - 48px);overflow:auto;background:#FFFFFF;border:1px solid #D2D5CD;border-radius:12px;box-shadow:0 20px 50px rgba(27,30,26,.18);padding:20px 22px')}>
      <div style={toReactStyle('display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:18px')}><div><strong id="remediation-action-title" style={toReactStyle('display:block;font-size:16px;margin-bottom:5px')}>{isRiskScope ? '위험 수용' : isPullRequestScope ? '업데이트 PR 생성' : '재검토 열기'}</strong><span style={toReactStyle('font-size:11.5px;color:#8B9086')}>{isRiskScope ? selectedTarget ? `${selectedTarget.repository.display_name} 저장소를 위험 수용 처리합니다.` : `CVE ${group.cve_count}건 · 저장소 ${group.repository_count}곳 · Open Alert ${group.open_alert_count}건을 위험 수용 처리합니다.` : isPullRequestScope ? `${actionableRepositoryCount}개 저장소의 ${pullRequestTargets.length}개 프로젝트에 업데이트 PR을 생성합니다.` : selectedTarget ? `${selectedTarget.repository.display_name} 저장소를 다시 검토 필요 상태로 변경합니다.` : '전체 위험 수용을 취소하고 다시 검토 필요 상태로 변경합니다.'}</span></div>{isPullRequestScope && <button type="button" aria-label="모달 닫기" onClick={closeActionModal} style={toReactStyle('display:flex;align-items:center;justify-content:center;width:28px;height:28px;font:400 22px/22px Arial,sans-serif;color:#737A71;background:none;border:0;border-radius:6px;padding:0;cursor:pointer')}>×</button>}</div>
      {isRiskScope ? <div>
        <div role="radiogroup" aria-label="위험 수용 사유" style={toReactStyle('display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px;margin-bottom:14px')}>
          {[...Object.entries(RISK_REASON_LABEL), ['other', '기타']].map(([value, label]) => <button key={value} type="button" role="radio" aria-checked={riskReason === value} onClick={() => { setRiskReason(value); if (value !== 'other') setActionNote(''); }} style={toReactStyle(`text-align:left;font-family:inherit;font-size:12px;line-height:18px;font-weight:700;color:${riskReason === value ? '#2F8F5B' : '#515250'};background:${riskReason === value ? '#E7F3EC' : '#F5F6F3'};border:1px solid ${riskReason === value ? '#8FD4B4' : '#E4E6E1'};border-radius:8px;padding:11px 12px;cursor:pointer`)}>{label}</button>)}
        </div>
        {riskReason === 'other' && <label style={toReactStyle('display:block;font-size:11px;color:#737A71;margin-bottom:14px')}>사유 *<textarea aria-label="기타 사유" value={actionNote} onChange={(event) => setActionNote(event.target.value)} rows={3} style={toReactStyle('display:block;width:100%;box-sizing:border-box;margin-top:6px;border:1px solid #D2D5CD;border-radius:7px;padding:8px 10px;resize:vertical;font:12px/18px inherit')} /></label>}
        <div style={toReactStyle('display:flex;justify-content:flex-end;gap:8px;border-top:1px solid #EEF0EE;padding-top:16px')}>
          <button type="button" onClick={closeActionModal} style={toReactStyle('font-family:inherit;font-size:12px;line-height:18px;font-weight:700;color:#5B6058;background:#FFFFFF;border:1px solid #D2D5CD;border-radius:7px;padding:8px 14px;cursor:pointer')}>취소</button>
          <button type="button" disabled={!riskReason || (riskReason === 'other' && !actionNote.trim()) || actionSubmitting} onClick={() => submitGroupAction('risk_accepted', riskReason === 'other' ? actionNote : null, riskReason)} style={toReactStyle(`font-family:inherit;font-size:12px;line-height:18px;font-weight:700;color:#FFFFFF;background:${riskReason && (riskReason !== 'other' || actionNote.trim()) && !actionSubmitting ? '#2F8F5B' : '#BFC7C1'};border:0;border-radius:7px;padding:8px 14px;cursor:${riskReason && (riskReason !== 'other' || actionNote.trim()) && !actionSubmitting ? 'pointer' : 'default'}`)}>{actionSubmitting ? '저장 중…' : '위험 수용'}</button>
        </div>
      </div> : isReopenScope ? <div style={toReactStyle('display:flex;justify-content:flex-end;gap:8px;border-top:1px solid #EEF0EE;padding-top:16px')}>
        <button type="button" onClick={closeActionModal} style={toReactStyle('font-family:inherit;font-size:12px;line-height:18px;font-weight:700;color:#5B6058;background:#FFFFFF;border:1px solid #D2D5CD;border-radius:7px;padding:8px 14px;cursor:pointer')}>취소</button>
        <button type="button" disabled={actionSubmitting} onClick={reopenGroup} style={toReactStyle(`font-family:inherit;font-size:12px;line-height:18px;font-weight:700;color:#FFFFFF;background:${actionSubmitting ? '#BFC7C1' : '#2F8F5B'};border:0;border-radius:7px;padding:8px 14px;cursor:${actionSubmitting ? 'default' : 'pointer'}`)}>{actionSubmitting ? '변경 중…' : '재검토 열기'}</button>
      </div> : isPullRequestScope ? <div>
        <div style={toReactStyle('display:flex;flex-direction:column;gap:8px;margin-bottom:18px')}>
          {pullRequestTargets.map((target) => <div key={target.id} style={toReactStyle('display:grid;grid-template-columns:minmax(150px,1fr) minmax(180px,1.2fr) minmax(150px,1fr);gap:14px;align-items:center;background:#F5F6F3;border-radius:8px;padding:11px 13px')}>
            <strong style={toReactStyle('font-size:11.5px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap')}>{target.repository.display_name}</strong>
            <span style={toReactStyle('font:500 10.5px/16px ui-monospace,monospace;color:#5B6058;overflow-wrap:anywhere')}>{formatDependencyFiles(target)}</span>
            <span style={toReactStyle('font:600 10.5px/16px ui-monospace,monospace;color:#2F8F5B')}>{formatCurrentVersions(target)} → {target.representative_patched_version ?? '없음'}</span>
          </div>)}
        </div>
        {actionNotice && <div role="status" style={toReactStyle('background:#FCEFE1;border:1px solid #E9C99A;border-radius:7px;padding:9px 12px;margin-bottom:14px;font-size:12px;color:#9A5A16')}>{actionNotice}</div>}
        <div style={toReactStyle('display:flex;align-items:center;justify-content:flex-end;gap:14px;border-top:1px solid #EEF0EE;padding-top:16px')}>
          <span style={toReactStyle('font:600 11px/18px inherit;color:#2F8F5B')}>
            {pullRequestPhase === 'created' && `✓ PR ${pullRequestBatch?.pull_requests?.length ?? 0}개 생성 완료`}
            {pullRequestPhase === 'verification_pending' && '✓ PR 병합 완료 · 해결 확인 대기'}
            {pullRequestPhase === 'closed' && '✓ PR 일괄 닫기 완료'}
          </span>
          <div style={toReactStyle('display:flex;justify-content:flex-end;gap:8px')}>
          {['ready', 'creating'].includes(pullRequestPhase) && <button type="button" disabled={actionSubmitting} onClick={createPullRequests} style={toReactStyle(`display:inline-flex;align-items:center;justify-content:center;gap:7px;min-width:104px;font-family:inherit;font-size:12px;line-height:18px;font-weight:700;color:#FFFFFF;background:${actionSubmitting ? '#7EAE92' : '#2F8F5B'};border:0;border-radius:7px;padding:8px 14px;cursor:${actionSubmitting ? 'default' : 'pointer'}`)}>{actionSubmitting && <span className="watchback-button-spinner" aria-hidden="true" />}<span>{actionSubmitting ? 'PR 생성 중…' : selectedTarget ? 'PR 생성' : 'PR 일괄 생성'}</span></button>}
          {['created', 'closing'].includes(pullRequestPhase) && <button type="button" disabled={actionSubmitting} onClick={closePullRequests} style={toReactStyle(`display:inline-flex;align-items:center;justify-content:center;gap:7px;min-width:104px;font-family:inherit;font-size:12px;line-height:18px;font-weight:700;color:#5B6058;background:#FFFFFF;border:1px solid #D2D5CD;border-radius:7px;padding:8px 14px;cursor:${actionSubmitting ? 'default' : 'pointer'}`)}>{pullRequestPhase === 'closing' && <span className="watchback-button-spinner watchback-button-spinner--muted" aria-hidden="true" />}<span>{pullRequestPhase === 'closing' ? 'PR 닫는 중…' : 'PR 일괄 닫기'}</span></button>}
          {['created', 'merging'].includes(pullRequestPhase) && <button type="button" disabled={actionSubmitting} onClick={mergePullRequests} style={toReactStyle(`display:inline-flex;align-items:center;justify-content:center;gap:7px;min-width:104px;font-family:inherit;font-size:12px;line-height:18px;font-weight:700;color:#FFFFFF;background:${actionSubmitting ? '#7EAE92' : '#2F8F5B'};border:0;border-radius:7px;padding:8px 14px;cursor:${actionSubmitting ? 'default' : 'pointer'}`)}>{actionSubmitting && <span className="watchback-button-spinner" aria-hidden="true" />}<span>{actionSubmitting ? 'PR 병합 중…' : 'PR 일괄 병합'}</span></button>}
          {pullRequestPhase === 'verification_pending' && <button type="button" disabled style={toReactStyle('display:inline-flex;align-items:center;justify-content:center;min-width:104px;font-family:inherit;font-size:12px;line-height:18px;font-weight:700;color:#5B6058;background:#EEF0EE;border:1px solid #DDE2DC;border-radius:7px;padding:8px 14px')}>✓ PR 병합 완료</button>}
          {pullRequestPhase === 'completed' && <button type="button" disabled style={toReactStyle('display:inline-flex;align-items:center;justify-content:center;min-width:104px;font-family:inherit;font-size:12px;line-height:18px;font-weight:700;color:#2F8F5B;background:#E7F3EC;border:1px solid #BFEBD7;border-radius:7px;padding:8px 14px')}>✓ 조치 완료</button>}
          </div>
        </div>
      </div> : null}
      </section>
    </div>}
    {actionNotice && !isPullRequestScope && <div role="status" style={toReactStyle('background:#FCEFE1;border:1px solid #E9C99A;border-radius:7px;padding:9px 12px;margin-bottom:16px;font-size:12px;color:#9A5A16')}>{actionNotice}</div>}
    <div className="watchback-detail-grid watchback-remediation-detail-grid" style={toReactStyle('display:grid;grid-template-columns:minmax(0,1.38fr) minmax(360px,1fr);gap:20px;align-items:start')}>
      <div style={toReactStyle('display:flex;flex-direction:column;gap:20px;min-width:0')}>
        {dataSource === 'db' && group.ai_summary && <AISummaryCard summary={group.ai_summary} />}
        <section style={toReactStyle('background:#FFFFFF;border:1px solid #E4E6E1;border-radius:12px;padding:20px 22px')}>
          <div style={toReactStyle('display:flex;align-items:center;gap:8px;margin-bottom:14px')}><strong style={toReactStyle('font-size:14px')}>변화 근거</strong></div>
          <EvidenceOverview group={group} onSelectCve={(cveId) => setExpandedCve(expandedCve === cveId ? null : cveId)} />
          <div className="watchback-remediation-cve-head" style={toReactStyle('display:grid;grid-template-columns:104px 100px minmax(140px,1fr) 60px 12px;gap:8px;padding:0 8px 9px;font-size:10.5px;font-weight:700;color:#8B9086;border-bottom:1px solid #E4E6E1')}><span>CVE</span><span>Change</span><span>영향 버전</span><span>Fix</span><span /></div>
          <div style={toReactStyle('display:flex;flex-direction:column')}>
            {group.vulnerabilities.map((item) => <CveEvidenceRow key={item.cve_id} item={item} expanded={expandedCve === item.cve_id} onToggle={() => setExpandedCve(expandedCve === item.cve_id ? null : item.cve_id)} />)}
          </div>
        </section>
      </div>
      <aside style={toReactStyle('display:flex;flex-direction:column;gap:16px;min-width:0;position:sticky;top:84px')}>
        {group.action_history?.length > 0 && <section aria-label="조치 이력" style={toReactStyle('background:#FFFFFF;border:1px solid #E4E6E1;border-radius:12px;padding:18px 20px')}>
          <div style={toReactStyle('display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:15px')}>
            <strong style={toReactStyle('display:block;font-size:14px;line-height:20px;color:#1B1E1A')}>조치 이력</strong>
          </div>
          <div style={toReactStyle('display:flex;flex-direction:column')}>
            {group.action_history.map((item, index) => <ActionHistoryRow key={item.id} item={item} totalTargetCount={group.targets.length} isLatest={index === 0} isLast={index === group.action_history.length - 1} />)}
          </div>
        </section>}
        <section style={toReactStyle('background:#FFFFFF;border:1px solid #E4E6E1;border-radius:12px;padding:20px')}>
          <div style={toReactStyle('display:flex;align-items:center;gap:8px;margin-bottom:14px')}><strong style={toReactStyle('font-size:14px')}>조치 대상</strong></div>
          <div style={toReactStyle('display:flex;flex-direction:column;gap:10px')}>
          {group.targets.map((target) => {
            const pullRequests = targetPullRequests(group, target);
            return <div key={target.id} style={toReactStyle('border:1px solid #E4E6E1;border-radius:9px;padding:14px')}>
            <div style={toReactStyle('display:flex;align-items:flex-start;justify-content:space-between;gap:16px;margin-bottom:14px')}>
              <div>
                {target.repository.source_kind === 'actual'
                  ? <a href={`https://github.com/${target.repository.full_name}`} target="_blank" rel="noreferrer" style={toReactStyle('display:block;width:fit-content;font-size:13px;line-height:20px;font-weight:700;color:#1B1E1A;text-decoration:none')}>{target.repository.display_name} ↗</a>
                  : <strong style={toReactStyle('display:block;font-size:13px;line-height:20px')}>{target.repository.display_name}</strong>}
                <span style={toReactStyle('font-size:11px;color:#8B9086')}>{target.repository.importance} 중요도 · {target.status === 'accepted' ? '위험 수용' : target.status === 'open' ? '검토 필요' : '해결됨'}</span>
              </div>
              <div style={toReactStyle('display:flex;align-items:center;gap:8px')}>
                {target.repository.source_kind === 'synthetic' && <span style={toReactStyle('font-size:9px;font-weight:600;color:#8B9086;background:#EEF0EE;border-radius:20px;padding:3px 7px')}>Demo 합성</span>}
                {pullRequests.map((pullRequest) => <a key={pullRequest.url} href={pullRequest.url} target="_blank" rel="noreferrer" style={toReactStyle('font-size:11px;font-weight:700;color:#2F8F5B;text-decoration:none;white-space:nowrap')}>PR #{pullRequest.number} ↗</a>)}
                {target.status === 'open' && <button type="button" onClick={() => { setActionScope(`risk:${target.id}`); setActionNotice(''); setActionNote(''); setRiskReason(''); }} style={toReactStyle('font-size:12px;font-weight:700;font-family:inherit;color:#5B6058;background:#FFFFFF;border:1px solid #D2D5CD;border-radius:7px;padding:8px 12px;cursor:pointer')}>위험 수용</button>}
                {target.status === 'accepted' && <button type="button" onClick={() => { setActionScope(`reopen:${target.id}`); setActionNotice(''); }} style={toReactStyle('font-size:12px;font-weight:700;font-family:inherit;color:#5B6058;background:#FFFFFF;border:1px solid #D2D5CD;border-radius:7px;padding:8px 12px;cursor:pointer')}>재검토 열기</button>}
                {target.status !== 'resolved' && <button type="button" onClick={() => { setActionScope(target.id); setActionNotice(''); setPullRequestBatch(null); setPullRequestPhase('ready'); }} style={toReactStyle('font-size:12px;font-weight:700;font-family:inherit;color:#FFFFFF;background:#2F8F5B;border:none;border-radius:7px;padding:8px 14px;cursor:pointer')}>조치하기</button>}
              </div>
            </div>
            <div style={toReactStyle('display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px 14px;padding:12px 0;border-top:1px solid #F0F1EE;border-bottom:1px solid #F0F1EE')}>
              <RepositoryMetric label="현재 사용 버전" value={formatCurrentVersions(target)} mono />
              <RepositoryMetric label="권장 수정 버전" value={target.representative_patched_version ?? '없음'} mono color="#2F8F5B" />
              <RepositoryMetric label="의존성 파일" value={formatDependencyFiles(target)} mono />
              {target.open_alert_count > 0
                ? <button type="button" aria-expanded={expandedAlertTarget === target.id} onClick={() => setExpandedAlertTarget(expandedAlertTarget === target.id ? null : target.id)} style={toReactStyle('min-width:0;text-align:left;font-family:inherit;color:#1B1E1A;background:none;border:0;padding:0;cursor:pointer')}><span style={toReactStyle('display:block;font-size:10.5px;color:#8B9086;margin-bottom:5px')}>Open Alert</span><strong style={toReactStyle('display:flex;align-items:center;gap:5px;font-size:12px;color:#1B1E1A')}>{target.open_alert_count}건 <span aria-hidden="true" style={toReactStyle('font-size:9px;color:#8B9086')}>{expandedAlertTarget === target.id ? '▼' : '▶'}</span></strong></button>
                : <RepositoryMetric label="Open Alert" value="0건" />}
            </div>
            {expandedAlertTarget === target.id && <div style={toReactStyle('display:flex;flex-direction:column;gap:7px;padding-top:12px')}>
              {target.alerts.filter((alert) => alert.state === 'open').map((alert) => {
                const alertNumber = alert.html_url?.split('/').filter(Boolean).at(-1);
                const alertCve = group.vulnerabilities.find((item) => (
                  item.alerts.some((linkedAlert) => linkedAlert.id === alert.id)
                ))?.cve_id;
                return <div key={alert.id} style={toReactStyle('display:flex;align-items:center;gap:12px;background:#F5F6F3;border-radius:7px;padding:9px 11px')}>
                  <strong style={toReactStyle('flex:1;min-width:0;font-size:11.5px;color:#1B1E1A;white-space:nowrap')}>{alertNumber ? `Dependabot #${alertNumber}` : 'Dependabot Alert'}</strong>
                  <span style={toReactStyle('flex:1;min-width:0;font:500 10px/16px ui-monospace,monospace;color:#6B7280;white-space:nowrap')}>{alertCve ?? 'CVE 확인 불가'}</span>
                  {alert.source_kind === 'actual' && alert.html_url
                    ? <a href={alert.html_url} target="_blank" rel="noreferrer" style={toReactStyle('font-size:11px;font-weight:600;color:#2F8F5B;text-decoration:none;white-space:nowrap')}>GitHub에서 보기 ↗</a>
                    : <span style={toReactStyle('font-size:9px;font-weight:600;color:#8B9086;background:#E7E9E5;border-radius:20px;padding:3px 7px;white-space:nowrap')}>Demo 합성</span>}
                </div>;
              })}
            </div>}
          </div>;
          })}
          </div>
        </section>
      </aside>
    </div>
  </main>;
}

function AISummaryCard({ summary }) {
  return <section aria-label="AI 요약" style={toReactStyle('background:#FFFFFF;border:1px solid #E4E6E1;border-radius:12px;padding:20px 22px')}>
    <div style={toReactStyle('display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:14px')}>
      <strong style={toReactStyle('font-size:14px')}>AI 요약</strong>
      <span aria-hidden="true" style={toReactStyle('font-size:14px;color:#2F8F5B')}>✦</span>
    </div>
    <AISummaryRow label="핵심 위험" text={summary.risk_summary} />
    {summary.interpretation_note && <div style={toReactStyle('margin-top:13px')}><AISummaryRow label="해석 주의" text={summary.interpretation_note} /></div>}
  </section>;
}

function AISummaryRow({ label, text }) {
  const emphasisPattern = new RegExp(
    `(${AI_SUMMARY_EMPHASIS_TERMS.map((term) => term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})`,
    'gi',
  );
  const parts = text.split(emphasisPattern);
  return <div><strong style={toReactStyle('display:block;font-size:11px;color:#737A71;margin-bottom:5px')}>{label}</strong><p style={toReactStyle('font-size:12.5px;line-height:1.65;color:#3F443D;margin:0')}>{parts.map((part, index) => (
    AI_SUMMARY_EMPHASIS_TERMS.some((term) => term.toLowerCase() === part.toLowerCase())
      ? <strong key={`${part}-${index}`} style={toReactStyle('font-weight:700;color:#1B1E1A')}>{part}</strong>
      : <Fragment key={`${part}-${index}`}>{part}</Fragment>
  ))}</p></div>;
}

function SummaryMetric({ left, label, value, color = '#1B1E1A', emphasis = false }) {
  return <div style={toReactStyle(`position:absolute;left:${left};top:113px;width:100px`)}><div style={toReactStyle('font-size:11px;line-height:15px;color:#7C8379;margin-bottom:5px')}>{label}</div><div style={toReactStyle(`font-size:12px;line-height:19px;font-weight:${emphasis ? '700' : '400'};color:${color};white-space:nowrap`)}>{value}</div></div>;
}

function RepositoryMetric({ label, value, mono = false, color = '#1B1E1A' }) {
  return <div style={toReactStyle('min-width:0')}><span style={toReactStyle('display:block;font-size:10.5px;color:#8B9086;margin-bottom:5px')}>{label}</span><strong style={toReactStyle(`${mono ? 'font-family:ui-monospace,monospace;font-size:11px;' : 'font-size:12px;'}display:block;color:${color};overflow-wrap:anywhere`)}>{value}</strong></div>;
}

function EvidenceOverview({ group, onSelectCve }) {
  const events = group.vulnerabilities.flatMap((vulnerability) => (
    (vulnerability.candidates ?? []).flatMap((candidate) => {
      const evidenceByObservedAt = new Map();
      (candidate.evidence ?? []).forEach((evidence) => {
        if (!evidence.observed_at) return;
        const observedDate = String(evidence.observed_at).slice(0, 10);
        if (!evidenceByObservedAt.has(observedDate)) evidenceByObservedAt.set(observedDate, []);
        evidenceByObservedAt.get(observedDate).push(evidence);
      });
      if (evidenceByObservedAt.size > 0) {
        return Array.from(evidenceByObservedAt.entries()).map(([dateKey, evidence]) => ({
          id: `${candidate.id}:${dateKey}`,
          cveId: vulnerability.cve_id,
          date: evidence[0].observed_at,
          label: TIMELINE_CHANGE_LABEL[candidate.change_type] ?? candidate.change_type,
          type: candidate.change_type,
          evidence,
        }));
      }
      return (candidate.deliveries ?? []).flatMap((delivery) => (
        (delivery.source_annotations ?? [])
          .filter((annotation) => annotation.snapshot_date)
          .map((annotation) => ({
            id: `${candidate.id}:${annotation.snapshot_date}:${annotation.annotation_type}`,
            cveId: vulnerability.cve_id,
            date: annotation.snapshot_date,
            label: annotation.label,
            type: candidate.change_type,
            evidence: [],
          }))
      ));
    })
  )).sort((left, right) => new Date(left.date) - new Date(right.date));
  if (events.length === 0) return null;
  const eventsByDate = new Map();
  events.forEach((event) => {
    const dateKey = String(event.date).slice(0, 10);
    if (!eventsByDate.has(dateKey)) eventsByDate.set(dateKey, []);
    eventsByDate.get(dateKey).push(event);
  });
  const groupedEvents = Array.from(eventsByDate.entries()).map(([dateKey, items]) => ({
    id: dateKey,
    date: items[0].date,
    items,
  }));
  return <div style={toReactStyle('margin-bottom:18px')}><EvidenceTimeline events={groupedEvents} onSelectCve={onSelectCve} /></div>;
}

function EvidenceTimeline({ events, onSelectCve }) {
  const [hoveredEventId, setHoveredEventId] = useState(null);
  return <section aria-label="변화 타임라인" style={toReactStyle('min-width:0;position:relative;padding:2px 0 4px')}>
    {events.length > 0
      ? <div style={{ position: 'relative', display: 'grid', gridTemplateColumns: `repeat(${events.length}, minmax(70px, 1fr))` }}>
          {events.length > 1 && <span aria-hidden="true" style={{ position: 'absolute', left: `calc(50% / ${events.length})`, right: `calc(50% / ${events.length})`, top: '8px', height: '1px', background: '#E4E7E2' }} />}
          {events.map((event, index) => {
            const primaryEvent = event.items[0];
            const color = event.items.some((item) => item.type === 'kev_new' || item.type === 'kev_added') ? '#C7402A' : event.items.some((item) => item.type === 'epss_top5_entry_d30') ? '#1F6FBF' : '#2F8F5B';
            const eventLabel = event.items.length > 1 ? `변화 ${event.items.length}건` : primaryEvent.label;
            const tooltip = [formatDate(event.date), ...event.items.flatMap((item) => [item.cveId, item.label])].join('\n');
            const tooltipPosition = index === 0
              ? { left: '6px' }
              : index === events.length - 1
                ? { right: '6px' }
                : { left: '50%', transform: 'translateX(-50%)' };
            const isHovered = hoveredEventId === event.id;
            return <button key={event.id} type="button" aria-label={tooltip.replaceAll('\n', ', ')} onMouseEnter={() => setHoveredEventId(event.id)} onMouseLeave={() => setHoveredEventId(null)} onFocus={() => setHoveredEventId(event.id)} onBlur={() => setHoveredEventId(null)} onClick={() => { setHoveredEventId(event.id); onSelectCve(primaryEvent.cveId); }} style={toReactStyle('position:relative;z-index:1;min-width:70px;text-align:center;font-family:inherit;background:none;border:0;padding:2px 6px 0;cursor:pointer')}>
              <span aria-hidden="true" style={toReactStyle(`display:block;width:10px;height:10px;border:1px solid ${isHovered ? color : '#D8DDD7'};border-radius:50%;background:${isHovered ? color : `${color}99`};box-shadow:${isHovered ? `0 0 0 3px ${color}24` : 'none'};margin:0 auto 8px;transition:border-color .15s,background .15s,box-shadow .15s`)} />
              <span style={toReactStyle(`display:block;font-size:9.5px;color:${isHovered ? '#737A71' : '#A1A69F'};margin-bottom:2px`)}>{formatDate(event.date)}</span>
              <strong style={toReactStyle(`display:block;font-size:10.5px;line-height:15px;font-weight:500;color:${isHovered ? '#1B1E1A' : '#5F655D'};white-space:nowrap`)}>{eventLabel}</strong>
              {hoveredEventId === event.id && <span role="tooltip" style={{ position: 'absolute', ...tooltipPosition, top: '58px', zIndex: 10, width: '190px', boxSizing: 'border-box', textAlign: 'left', color: '#1B1E1A', background: '#FFFFFF', border: '1px solid #DDE2DC', borderRadius: '8px', boxShadow: '0 8px 22px rgba(27,30,26,.14)', padding: '9px 11px' }}>
                {event.items.map((item, itemIndex) => <span key={item.id} style={toReactStyle(`${itemIndex > 0 ? 'border-top:1px solid #EEF0EE;padding-top:7px;margin-top:7px;' : ''}display:block`)}>
                  <strong style={toReactStyle('display:block;font:600 10.5px/17px Inter,Arial,sans-serif;margin-bottom:2px')}>{item.cveId}</strong>
                  <span style={toReactStyle('display:flex;align-items:center;gap:7px;flex-wrap:wrap;font-size:10.5px;line-height:17px')}>
                    {item.evidence.length > 0
                      ? item.evidence.map((evidence) => <TimelineEvidenceSummary key={evidence.id} evidence={evidence} />)
                      : <span style={toReactStyle('color:#5B6058')}>{item.label}</span>}
                  </span>
                </span>)}
              </span>}
            </button>;
          })}
        </div>
      : <span style={toReactStyle('font-size:11px;color:#8B9086')}>표시할 변화가 없습니다.</span>}
  </section>;
}

function TimelineEvidenceSummary({ evidence }) {
  if (evidence.signal === 'epss_score_d30') {
    const delta = (Number(evidence.current_value) - Number(evidence.previous_value)) * 100;
    return <span style={toReactStyle('font-weight:600;color:#2F8F5B')}>↑ EPSS {Number.isFinite(delta) ? `+${delta.toFixed(1).replace(/\.0$/, '')}%p` : '상승'}</span>;
  }
  if (evidence.signal === 'epss_percentile_d30') {
    return <span style={toReactStyle('font-weight:600;color:#1F6FBF')}>↑ {formatEvidenceValue(evidence.current_value, evidence)} 진입</span>;
  }
  if (evidence.signal === 'kev') {
    return <span style={toReactStyle('font-weight:600;color:#C7402A')}>CISA KEV 신규 등재</span>;
  }
  return <span style={toReactStyle('color:#5B6058')}>{SIGNAL_LABEL[evidence.signal] ?? evidence.signal}</span>;
}

function CveEvidenceRow({ item, expanded, onToggle }) {
  const representativeCandidate = [...item.candidates].sort((left, right) => (
    (CANDIDATE_PRIORITY_ORDER[left.priority] ?? 99) - (CANDIDATE_PRIORITY_ORDER[right.priority] ?? 99) ||
    new Date(right.selected_at) - new Date(left.selected_at)
  ))[0];
  const representativeChangeType = representativeCandidate.change_type;
  const changeTag = {
    kev_new: { label: 'NEW KEV', style: 'color:#A6321B;background:#FBEAE6;border:1px solid #FFCABD' },
    kev_added: { label: 'NEW KEV', style: 'color:#A6321B;background:#FBEAE6;border:1px solid #FFCABD' },
    epss_rise_d30: { label: 'EPSS 급등', style: 'color:#2F8F5B;background:#E7F3EC;border:1px solid #BFEBD7' },
    epss_top5_entry_d30: { label: 'EPSS 상위 5%', style: 'color:#1F6FBF;background:#E6EFFA;border:1px solid #C5D8F0' },
  }[representativeChangeType] ?? { label: CHANGE_LABEL[representativeChangeType] ?? representativeChangeType, style: 'color:#5B6058;background:#EEF0EE;border:1px solid #DDE2DC' };
  const affectedVersion = item.affected_versions.join(', ') || '-';
  return <div style={toReactStyle('border-bottom:1px solid #EEF0EE')}>
    <button type="button" aria-expanded={expanded} onClick={onToggle} className="watchback-remediation-cve-row" style={toReactStyle('width:100%;display:grid;grid-template-columns:104px 100px minmax(140px,1fr) 60px 12px;gap:8px;align-items:center;text-align:left;font-family:inherit;color:#1B1E1A;background:#FFFFFF;border:0;padding:13px 8px;cursor:pointer')}><strong style={toReactStyle('font:600 11.5px/18px Inter,Arial,sans-serif')}>{item.cve_id}</strong><span style={toReactStyle(`justify-self:start;width:fit-content;font-size:8.5px;font-weight:600;border-radius:12px;padding:2px 6px;white-space:nowrap;${changeTag.style}`)}>{changeTag.label}</span><span style={toReactStyle('font:500 10px/17px ui-monospace,monospace;color:#5B6058')}>{affectedVersion}</span><span style={toReactStyle('font:600 10.5px/18px ui-monospace,monospace;color:#2F8F5B')}>{item.representative_patched_version ?? '없음'}</span><span aria-hidden="true" style={toReactStyle('font-size:9px;color:#8B9086')}>{expanded ? '▼' : '▶'}</span></button>
    {expanded && <div style={toReactStyle('background:#FAFBFA;padding:4px 12px 14px')}><div style={toReactStyle('display:flex;align-items:flex-start;justify-content:space-between;gap:14px;margin-bottom:12px')}><div style={toReactStyle('font-size:12px;line-height:19px;color:#515250')}>{item.advisory.summary}</div><div style={toReactStyle('flex-shrink:0;display:flex;align-items:center;gap:10px;padding-top:1px')}><a href={`https://nvd.nist.gov/vuln/detail/${encodeURIComponent(item.cve_id)}`} target="_blank" rel="noreferrer" style={toReactStyle('font-size:10.5px;font-weight:600;color:#2F8F5B;text-decoration:none;white-space:nowrap')}>CVE 상세 ↗</a>{item.ghsa_id && <a href={`https://github.com/advisories/${encodeURIComponent(item.ghsa_id)}`} target="_blank" rel="noreferrer" style={toReactStyle('font-size:10.5px;font-weight:600;color:#2F8F5B;text-decoration:none;white-space:nowrap')}>GitHub Advisory ↗</a>}</div></div>{item.candidates.map((candidate) => <div key={candidate.id} style={toReactStyle('border-left:2px solid #D2D5CD;padding-left:12px;margin-top:11px')}>
      <div style={toReactStyle('display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:10px')}><strong style={toReactStyle('font-size:12px')}>{CHANGE_LABEL[candidate.change_type] ?? candidate.change_type}</strong><span style={toReactStyle('font-size:10px;color:#8B9086')}>후보 선정 {formatDate(candidate.selected_at)}</span></div>
      {(candidate.deliveries ?? []).flatMap((delivery) => delivery.source_annotations ?? []).map((annotation) => <div key={`${annotation.snapshot_date}-${annotation.annotation_type}`} style={toReactStyle('font-size:11px;line-height:18px;color:#7A521F;background:#FCEFE1;border-radius:7px;padding:9px 10px;margin-bottom:9px')}><strong>{annotation.label}</strong> · {annotation.description} {annotation.source_url && <a href={annotation.source_url} target="_blank" rel="noreferrer" style={toReactStyle('color:#9A5A16;font-weight:700')}>출처 보기 ↗</a>}</div>)}
      <div style={toReactStyle('display:flex;flex-direction:column;gap:8px')}>
        {(candidate.evidence ?? []).map((evidence) => <EvidenceCard
          key={evidence.id}
          signalLabel={SIGNAL_LABEL[evidence.signal] ?? evidence.signal}
          previousValueLabel={formatEvidenceValue(evidence.previous_value, evidence)}
          currentValueLabel={formatEvidenceValue(evidence.current_value, evidence)}
          observedLabel={formatDate(evidence.observed_at)}
          reasonSummary={formatEvidenceDescription(evidence)}
        />)}
      </div>
    </div>)}</div>}
  </div>;
}
