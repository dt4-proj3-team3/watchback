'use client';

import { Component } from 'react';
import { useRouter } from 'next/navigation';
import { Dashboard } from './dashboard';
import { Header } from './header';
import { Repositories } from './repositories';
import { ReviewCaseDetail } from './review-case-detail';
import { ReviewCaseList } from './review-case-list';
import { ReviewDataState } from './review-data-state';
import { Settings } from './settings';

const PRIORITY_META = {
  critical: { label: '치명적', bg: '#FBEAE6', text: '#A6321B', border: '#E3B6AA', dot: '#C7402A' },
  high:     { label: '높음',   bg: '#FCEFE1', text: '#9A5A16', border: '#E9C99A', dot: '#C7752A' },
  medium:   { label: '보통',   bg: '#FBF3D9', text: '#8A6A05', border: '#E4D28C', dot: '#B08900' },
  low:      { label: '낮음',   bg: '#EEF0EE', text: '#5A6058', border: '#D2D5CD', dot: '#8B9086' },
};
const CHANGE_TYPE_LABEL = {
  kev_added: 'KEV 신규 등재',
  epss_spike: 'EPSS 급등',
  epss_rise_d30: 'EPSS 급등',
  epss_top5_entry_d30: 'EPSS 상위 5% 진입',
  patch_available: '패치 버전 등장',
  combined_signal: '다중 신호 동시 변화',
};
const SIGNAL_LABEL = {
  kev: 'CISA KEV 등재',
  epss: 'EPSS 점수',
  epss_score_d30: 'EPSS 악용 가능성',
  epss_percentile_d30: '전체 CVE 상대 순위',
  patch: '패치 버전',
  cvss: 'CVSS 점수',
  advisory_severity: '권고 심각도',
};
const ACTIVITY_LABEL = {
  case_opened: 'Case 생성', case_reopened: 'Case 재오픈', case_resolved: 'Case 해결',
  review_deferred: '재검토 보류', risk_accepted: '위험 수용', remediation_requested: '조치 요청',
  note_added: '메모 추가', external_link_added: '외부 링크 연결',
};
const SCOPE_LABEL = { runtime: '런타임', development: '개발' };
const REL_LABEL = { direct: '직접 의존성', transitive: '간접 의존성', unknown: '확인 불가' };

function fmtDate(iso) {
  if (!iso) return '-';
  const d = new Date(iso);
  return `${d.getFullYear()}.${String(d.getMonth() + 1).padStart(2, '0')}.${String(d.getDate()).padStart(2, '0')}`;
}

function fmtEvidenceValue(value, valueType, signal) {
  if (signal === 'kev') {
    if (value === 'false') return '미등재';
    if (value === 'true') return '등재';
  }
  if (valueType !== 'decimal' || value == null || value === '') return value;
  const number = Number(value);
  if (!Number.isFinite(number)) return value;
  if (signal === 'epss_percentile_d30') {
    return `${(number * 100).toFixed(1).replace(/\.0$/, '')} 백분위`;
  }
  if (signal === 'epss_score_d30') {
    const percent = number * 100;
    const digits = percent > 0 && percent < 0.1 ? 2 : 1;
    return `${percent.toFixed(digits).replace(/\.0+$/, '')}%`;
  }
  return number.toFixed(4).replace(/\.?0+$/, '');
}

function fmtEvidenceReason(reason, signal, currentValue) {
  if (signal === 'epss_percentile_d30') {
    const percentile = Number(currentValue);
    if (Number.isFinite(percentile)) {
      return `전체 CVE 중 상위 ${((1 - percentile) * 100).toFixed(1).replace(/\.0$/, '')}%에 해당합니다.`;
    }
  }
  return reason.replace(/^\d{4}-\d{2}-\d{2}\s+/, '');
}

function formatReviewReason(reason) {
  const match = reason.match(/^(\d{4})-(\d{2})-(\d{2})\s+(.+)$/);
  if (!match) return { dateLabel: null, text: reason };
  return { dateLabel: `${match[1]}.${match[2]}.${match[3]}`, text: match[4] };
}

function badgeStyle(meta) {
  return `font-size:11px;font-weight:600;color:${meta.text};background:${meta.bg};border-radius:20px;padding:3px 9px;white-space:nowrap`;
}

function evidenceTags(evidence = []) {
  const hasKevAdded = evidence.some(item => item.signal === 'kev' && item.previous_value === 'false' && item.current_value === 'true');
  const hasEpssSpike = evidence.some(item => item.signal === 'epss_score_d30' && Number(item.current_value) > Number(item.previous_value));
  const hasTopFiveEntry = evidence.some(item => (
    item.signal === 'epss_percentile_d30' &&
    Number(item.previous_value) < 0.95 &&
    Number(item.current_value) >= 0.95
  ));

  const tags = [];
  if (hasKevAdded) {
    tags.push({ label: 'KEV 등재', style: 'font-size:11px;font-weight:600;color:#A6321B;background:#FBEAE6;border-radius:5px;padding:2px 7px;white-space:nowrap' });
  }
  if (hasEpssSpike) {
    tags.push({ label: 'EPSS 급등', style: 'font-size:11px;font-weight:600;color:#2F8F5B;background:#E7F3EC;border-radius:5px;padding:2px 7px;white-space:nowrap' });
  }
  if (tags.length < 2 && hasTopFiveEntry) {
    tags.push({ label: '상위 5%', style: 'font-size:11px;font-weight:600;color:#1F6FBF;background:#E6EFFA;border-radius:5px;padding:2px 7px;white-space:nowrap' });
  }
  return tags.slice(0, 2);
}

function latestCandidateTags(candidate) {
  if (!candidate) return [];
  const labels = {
    kev_added: 'KEV 등재',
    epss_spike: 'EPSS 급등',
    epss_rise_d30: 'EPSS 급등',
    epss_top5_entry_d30: '상위 5%',
    patch_available: '패치 등장',
    combined_signal: '다중 신호',
  };
  const label = labels[candidate.change_type];
  return label ? [{ label, style: 'font-size:11px;font-weight:600;color:#2F8F5B;background:#E7F3EC;border-radius:5px;padding:2px 7px;white-space:nowrap' }] : [];
}

export function filterAndSortCases(cases, filters, now = Date.now()) {
  let list = cases.filter(c => filters.status === 'all' || c.status === filters.status);
  if (filters.priority !== 'all') list = list.filter(c => c.priority === filters.priority);
  if (filters.changeType !== 'all') list = list.filter(c => c.latest_candidate.change_type === filters.changeType);
  if (filters.importance && filters.importance !== 'all') list = list.filter(c => c.repository.importance === filters.importance);
  if (filters.staleOnly) list = list.filter(c => (now - new Date(c.opened_at)) / 86400000 >= 3);
  if (filters.repo && filters.repo !== 'all') list = list.filter(c => c.repository.full_name === filters.repo);

  const order = { critical: 0, high: 1, medium: 2, low: 3 };
  if (filters.sort === 'priority') return [...list].sort((a, b) => order[a.priority] - order[b.priority] || new Date(b.updated_at) - new Date(a.updated_at));
  if (filters.sort === 'updated_at') return [...list].sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at));
  return [...list].sort((a, b) => new Date(b.opened_at) - new Date(a.opened_at));
}


class WatchbackAppView extends Component {
  state = {
    view: this.props.initialView,
    previousView: this.props.initialView === 'detail' ? 'list' : this.props.initialView,
    selectedId: this.props.initialSelectedId,
    filters: { status: 'open', priority: 'all', changeType: 'all', importance: 'all', staleOnly: false, repo: 'all', sort: 'priority' },
    showActivityForm: false,
    activityKind: null,
    noteDraft: '',
    linkType: '',
    linkUrl: '',
    showPrUnavailableNotice: false,
    cases: this.props.initialCases,
    repoImportanceOverrides: {},
    policyMatrix: {
      'critical_critical': 'pr_only', 'critical_high': 'pr_only', 'critical_medium': 'pr_only', 'critical_low': 'pr_only',
      'high_critical': 'pr_only', 'high_high': 'pr_only', 'high_medium': 'pr_only', 'high_low': 'pr_only',
      'medium_critical': 'pr_only', 'medium_high': 'pr_only', 'medium_medium': 'pr_only', 'medium_low': 'pr_only',
      'low_critical': 'pr_only', 'low_high': 'pr_only', 'low_medium': 'pr_only', 'low_low': 'pr_only',
    },
  };

  componentDidUpdate(previousProps) {
    if (
      previousProps.initialView !== this.props.initialView ||
      previousProps.initialSelectedId !== this.props.initialSelectedId
    ) {
      this.setState({
        view: this.props.initialView,
        selectedId: this.props.initialSelectedId,
        showActivityForm: false,
        showPrUnavailableNotice: false,
      });
    }
  }

  componentWillUnmount() {
    clearTimeout(this.prNoticeTimer);
    clearTimeout(this.previewNoticeTimer);
  }

  enrich(c) {
    const pm = PRIORITY_META[c.priority];
    const im = PRIORITY_META[c.repository.importance];
    const sm = PRIORITY_META[c.advisory.severity];
    const reviewReason = formatReviewReason(c.review_reason);
    return {
      ...c,
      repoName: c.repository.display_name,
      repositoryUrl: `https://github.com/${c.repository.full_name}`,
      priorityLabel: pm.label,
      priorityDot: pm.dot,
      priorityBadgeStyle: badgeStyle(pm),
      importanceLabel: im.label,
      importanceBadgeStyle: badgeStyle(im),
      severityLabel: sm.label,
      severityBadgeStyle: badgeStyle(sm),
      changeTypeLabel: CHANGE_TYPE_LABEL[c.latest_candidate.change_type] || c.latest_candidate.change_type,
      evidenceTags: evidenceTags(c.evidence).length > 0 ? evidenceTags(c.evidence) : latestCandidateTags(c.latest_candidate),
      reviewReasonLabel: reviewReason.text,
      reviewReasonDateLabel: reviewReason.dateLabel,
      isResolved: c.status === 'resolved',
      isReopened: c.reopened_count > 0,
      openedLabel: fmtDate(c.opened_at),
      updatedLabel: fmtDate(c.updated_at),
      onOpen: () => this.openCase(c.id),
    };
  }

  openCase(id) {
    this.props.router.push(`/review-cases/${id}`);
  }

  backToList() {
    this.props.router.push('/review-cases');
  }

  goToDashboard() { this.props.router.push('/dashboard'); }
  goToAllList() { this.props.router.push('/review-cases'); }

  goToFilteredList(filters) {
    this.setState({ filters });
    this.props.router.push('/review-cases');
  }

  setStatusFilter(v) { this.setState(s => ({ filters: { ...s.filters, status: v } })); }
  setPriorityFilter(v) { this.setState(s => ({ filters: { ...s.filters, priority: v } })); }
  setChangeTypeFilter(v) { this.setState(s => ({ filters: { ...s.filters, changeType: v } })); }
  setSort(v) { this.setState(s => ({ filters: { ...s.filters, sort: v } })); }
  openActivityForm(kind) { this.setState({ showActivityForm: true, activityKind: kind, noteDraft: '', linkType: '', linkUrl: '' }); }
  cancelActivityForm() { this.setState({ showActivityForm: false, activityKind: null }); }

  showPrUnavailableNotice() {
    this.setState({ showPrUnavailableNotice: true });
    clearTimeout(this.prNoticeTimer);
    this.prNoticeTimer = setTimeout(() => this.setState({ showPrUnavailableNotice: false }), 3000);
  }


  showPreviewNotice() {
    this.setState({ showPreviewNotice: true, showActivityForm: false });
    clearTimeout(this.previewNoticeTimer);
    this.previewNoticeTimer = setTimeout(() => this.setState({ showPreviewNotice: false }), 3000);
  }

  submitActivity() {
    this.showPreviewNotice();
  }

  renderVals() {
    const { filters, view, selectedId, showActivityForm, activityKind, noteDraft, linkType, linkUrl } = this.state;
    const cases = this.props.initialCases;
    const isDemo = this.props.dataSource === 'demo';

    const order = { critical: 0, high: 1, medium: 2, low: 3 };
    const list = filterAndSortCases(cases, filters);

    const filteredCases = list.map(c => this.enrich(c));
    const isEmpty = filteredCases.length === 0;
    const openTotal = cases.filter(c => c.status === 'open').length;
    const resolvedTotal = cases.filter(c => c.status === 'resolved').length;
    const inProgressTotal = cases.filter(c => c.status === 'open' && c.activities.some(a => a.activity_type === 'remediation_requested')).length;

    const navTabs = [
      { key: 'dashboard', label: '대시보드', onClick: () => this.props.router.push('/dashboard') },
      { key: 'list', label: '재검토 목록', onClick: () => this.props.router.push('/review-cases') },
      { key: 'repos', label: '저장소', onClick: () => this.props.router.push('/repositories') },
      { key: 'settings', label: '설정', onClick: () => this.props.router.push('/settings') },
    ].map(t => {
      const active = (t.key === 'dashboard' && view === 'dashboard') || (t.key === 'list' && (view === 'list' || view === 'detail')) || (t.key === 'repos' && view === 'repos') || (t.key === 'settings' && view === 'settings');
      return { ...t, style: `font-size:13px;font-weight:600;padding:8px 12px;border-radius:7px;cursor:pointer;color:${active ? '#1B1E1A' : '#8B9086'};background:${active ? '#EEF0EE' : 'transparent'}` };
    });

    const MODE_COLOR = { fully_auto: '#2F8F5B', click_to_merge: '#1F6FBF', pr_only: '#9A5A16' };
    const MODE_BG = { fully_auto: '#E7F3EC', click_to_merge: '#E6EFFA', pr_only: '#FCEFE1' };
    const importanceLevels = ['critical', 'high', 'medium', 'low'];
    const repoMap = new Map();
    cases.forEach(c => {
      const key = c.repository.full_name;
      if (!repoMap.has(key)) repoMap.set(key, { ...c.repository, openCount: 0, criticalOpenCount: 0 });
      const r = repoMap.get(key);
      if (c.status === 'open') {
        r.openCount += 1;
        if (c.priority === 'critical') r.criticalOpenCount += 1;
      }
    });
    const repoRows = Array.from(repoMap.values()).map(r => {
      const currentImportance = this.state.repoImportanceOverrides[r.full_name] || r.importance;
      const im = PRIORITY_META[currentImportance];
      const exceptions = importanceLevels
        .map(sev => ({ sev, sevLabel: PRIORITY_META[sev].label, mode: this.state.policyMatrix[`${currentImportance}_${sev}`] }))
        .filter(p => p.mode !== 'fully_auto');
      const allModes = importanceLevels.map(sev => this.state.policyMatrix[`${currentImportance}_${sev}`]);
      const demoPolicySummary = allModes.every(mode => mode === 'pr_only')
        ? { label: '전체 PR 생성만', color: MODE_COLOR.pr_only, bg: MODE_BG.pr_only }
        : exceptions.length === 0
        ? { label: '전체 자동조치', color: MODE_COLOR.fully_auto, bg: MODE_BG.fully_auto }
        : { label: `${exceptions.map(e => e.sevLabel).join('·')} 심각도는 승인 필요`, color: MODE_COLOR[exceptions[0].mode], bg: MODE_BG[exceptions[0].mode] };
      const policySummary = isDemo
        ? demoPolicySummary
        : { label: '정책 DB 연동 미구현', color: '#8B9086', bg: '#EEF0EE' };
      return {
        ...r,
        importance: currentImportance,
        importanceLabel: im.label,
        importanceBadgeStyle: badgeStyle(im),
        policySummary,
        onOpen: () => {
          this.setState({ filters: { ...filters, repo: r.full_name, status: 'all', importance: 'all', staleOnly: false } });
          this.props.router.push('/review-cases');
        },
        onImportanceChange: () => this.showPreviewNotice(),
      };
    }).sort((a, b) => order[a.importance] - order[b.importance]);

    const policyMatrixRows = importanceLevels.map(imp => ({
      importanceLabel: PRIORITY_META[imp].label,
      cells: importanceLevels.map(sev => {
        const key = `${imp}_${sev}`;
        const mode = this.state.policyMatrix[key];
        return {
          severityLabel: PRIORITY_META[sev].label,
          value: mode,
          onChange: () => this.showPreviewNotice(),
        };
      }),
    }));

    const topCases = cases
      .filter(c => c.status === 'open')
      .sort((a, b) => order[a.priority] - order[b.priority] || new Date(b.updated_at) - new Date(a.updated_at))
      .slice(0, 5)
      .map(c => {
        const e = this.enrich(c);
        const daysOpen = Math.floor((Date.now() - new Date(c.opened_at)) / 86400000);
        const urgencyLabel = c.reopened_count > 0 ? `재오픈 ${c.reopened_count}회` : (daysOpen >= 3 ? `${daysOpen}일째 미처리` : null);
        const patchLabel = c.latest_candidate.change_type === 'patch_available' && c.alert.first_patched_version ? `패치 ${c.alert.first_patched_version}` : null;
        return { ...e, urgencyLabel, patchLabel };
      });

    const criticalOpenCount = cases.filter(c => c.status === 'open' && c.repository.importance === 'critical').length;
    const staleCount = cases.filter(c => c.status === 'open' && (Date.now() - new Date(c.opened_at)) / 86400000 >= 3).length;

    const kpiCards = [
      { label: 'critical 저장소 미처리', value: `${criticalOpenCount}건`, hint: '가장 중요한 저장소에 열려있는 항목', trend: isDemo ? '지난주 대비 ▲1건' : '기간 비교 미연동', cursorStyle: 'pointer', onClick: () => this.goToFilteredList({ ...filters, status: 'open', importance: 'critical', staleOnly: false }) },
      { label: '3일 이상 미처리', value: `${staleCount}건`, hint: '재검토 대상이 된 지 오래된 항목', trend: isDemo ? '지난주 대비 변화 없음' : '기간 비교 미연동', cursorStyle: 'pointer', onClick: () => this.goToFilteredList({ ...filters, status: 'open', importance: 'all', staleOnly: true, sort: 'opened_at' }) },
      { label: '시스템성 변동 억제 (미구현)', value: isDemo ? '3건' : '—', hint: 'S1 제외 범위인 UI 미리보기', trend: isDemo ? 'Demo 데이터' : '실제 집계 미연동', cursorStyle: isDemo ? 'pointer' : 'default', onClick: isDemo ? () => this.setState({ showSuppressedPopover: true }) : undefined },
    ];

    const flowStages = [
      { label: '열림', count: openTotal - inProgressTotal, hasArrow: true, onClick: () => this.goToFilteredList({ ...filters, status: 'open', importance: 'all', staleOnly: false }) },
      { label: '조치 요청됨', count: inProgressTotal, hasArrow: true, onClick: () => this.goToFilteredList({ ...filters, status: 'open', importance: 'all', staleOnly: false }) },
      { label: '해결됨', count: resolvedTotal, hasArrow: false, onClick: () => this.goToFilteredList({ ...filters, status: 'resolved', importance: 'all', staleOnly: false }) },
    ].map(s => ({ ...s, containerStyle: 'display:flex;align-items:center;flex:none' }));

    const suppressedCases = isDemo ? [
      { repoName: 'billing-worker', reason: '모델 개편으로 EPSS가 전반적으로 상승, 개별 위험 변화로 보지 않음' },
      { repoName: 'notification-svc', reason: '동일 사유로 억제됨' },
      { repoName: 'auth-gateway', reason: '동일 사유로 억제됨' },
    ] : [];

    const statusOptions = [
      { value: 'open', label: '열림' },
      { value: 'resolved', label: '해결됨' },
      { value: 'all', label: '전체' },
    ].map(o => ({
      ...o,
      onClick: () => this.setStatusFilter(o.value),
      pillStyle: `font-size:12.5px;font-weight:600;padding:6px 12px;border-radius:6px;cursor:pointer;${filters.status === o.value ? 'background:#FFFFFF;color:#1B1E1A;box-shadow:0 1px 2px rgba(0,0,0,.06)' : 'background:transparent;color:#8B9086'}`,
    }));

    const priorityChipOptions = [{ value: 'all', label: '전체', dot: '#8B9086' }, ...Object.keys(PRIORITY_META).map(k => ({ value: k, label: PRIORITY_META[k].label, dot: PRIORITY_META[k].dot }))].map(o => {
      const active = filters.priority === o.value;
      return {
        ...o,
        onClick: () => this.setPriorityFilter(o.value),
        pillStyle: `display:flex;align-items:center;gap:6px;font-size:12.5px;font-weight:600;padding:6px 12px;border-radius:20px;cursor:pointer;border:1px solid ${active ? PRIORITY_META[o.value] ? PRIORITY_META[o.value].border : '#D2D5CD' : '#E4E6E1'};background:${active ? (PRIORITY_META[o.value] ? PRIORITY_META[o.value].bg : '#EEF0EE') : '#FFFFFF'};color:${active ? (PRIORITY_META[o.value] ? PRIORITY_META[o.value].text : '#1B1E1A') : '#5B6058'}`,
      };
    });
    const changeTypeChipOptions = [{ value: 'all', label: '전체' }, ...Object.keys(CHANGE_TYPE_LABEL).map(k => ({ value: k, label: CHANGE_TYPE_LABEL[k] }))].map(o => {
      const active = filters.changeType === o.value;
      return {
        ...o,
        onClick: () => this.setChangeTypeFilter(o.value),
        pillStyle: `font-size:12.5px;font-weight:600;padding:6px 12px;border-radius:20px;cursor:pointer;border:1px solid ${active ? '#2F8F5B' : '#E4E6E1'};background:${active ? '#E7F3EC' : '#FFFFFF'};color:${active ? '#2F8F5B' : '#5B6058'}`,
      };
    });
    const importanceChipOptions = [{ value: 'all', label: '전체', dot: '#8B9086' }, ...Object.keys(PRIORITY_META).map(k => ({ value: k, label: PRIORITY_META[k].label, dot: PRIORITY_META[k].dot }))].map(o => {
      const active = (filters.importance || 'all') === o.value;
      return {
        ...o,
        onClick: () => this.setState(s => ({ filters: { ...s.filters, importance: o.value } })),
        pillStyle: `display:flex;align-items:center;gap:6px;font-size:12.5px;font-weight:600;padding:6px 12px;border-radius:20px;cursor:pointer;border:1px solid ${active ? (PRIORITY_META[o.value] ? PRIORITY_META[o.value].border : '#D2D5CD') : '#E4E6E1'};background:${active ? (PRIORITY_META[o.value] ? PRIORITY_META[o.value].bg : '#EEF0EE') : '#FFFFFF'};color:${active ? (PRIORITY_META[o.value] ? PRIORITY_META[o.value].text : '#1B1E1A') : '#5B6058'}`,
      };
    });
    const staleToggle = {
      active: !!filters.staleOnly,
      onClick: () => this.setState(s => ({ filters: { ...s.filters, staleOnly: !s.filters.staleOnly } })),
      pillStyle: `font-size:12.5px;font-weight:600;padding:6px 12px;border-radius:20px;cursor:pointer;border:1px solid ${filters.staleOnly ? '#9A5A16' : '#E4E6E1'};background:${filters.staleOnly ? '#FCEFE1' : '#FFFFFF'};color:${filters.staleOnly ? '#9A5A16' : '#5B6058'}`,
    };

    let selected = null;
    const selectedCase = selectedId ? cases.find(c => c.id === selectedId) : null;
    if (selectedCase) {
      const raw = selectedCase;
      const e = this.enrich(raw);
      const effectiveImportance = this.state.repoImportanceOverrides[raw.repository.full_name] || raw.repository.importance;
      const configuredMergeMode = isDemo && raw.alert.first_patched_version
        ? this.state.policyMatrix[`${effectiveImportance}_${raw.advisory.severity}`]
        : null;
      const automation = {
        ...raw.automation,
        eligible: !!configuredMergeMode,
        mergeMode: configuredMergeMode,
        reason: configuredMergeMode
          ? '저장소 자동조치 정책에 따라 업데이트 PR을 생성할 수 있습니다.'
          : '패치 버전이 없어 업데이트 PR을 생성할 수 없습니다.',
      };
      selected = {
        ...e,
        automation,
        scopeLabel: SCOPE_LABEL[raw.alert.dependency_scope] || '-',
        relationshipLabel: REL_LABEL[raw.alert.dependency_relationship] || '-',
        hasKnownRelationship: raw.alert.dependency_relationship !== 'unknown',
        systemicLabel: '개별 변화로 확인됨',
        systemicColor: '#2F8F5B',
        systemicBg: '#E7F3EC',
        automationStatusLabel: { fully_auto: '완전 자동조치 (미구현)', click_to_merge: 'PR 병합 대기 (미구현)', pr_only: 'PR 생성 대상 (미구현)' }[configuredMergeMode] || '자동조치 미구현',
        automationStatusColor: automation.eligible ? '#2F8F5B' : '#8B9086',
        automationStatusBg: automation.eligible ? '#E7F3EC' : '#EEF0EE',
        hasPr: !!automation.prUrl,
        mergeMode: configuredMergeMode,
        patchLabelShort: raw.alert.first_patched_version || '패치 없음',
        patchColor: raw.alert.first_patched_version ? '#2F8F5B' : '#8B9086',
        evidenceGroups: raw.candidates.map(candidate => ({
          id: candidate.id,
          selectedLabel: fmtDate(candidate.selected_at),
          changeTypeLabel: CHANGE_TYPE_LABEL[candidate.change_type] || candidate.change_type,
          reasonSummary: candidate.reason_summary,
          deliveries: candidate.deliveries ?? [],
          evidence: (candidate.evidence ?? []).map(ev => ({
            ...ev,
            previousValueLabel: fmtEvidenceValue(ev.previous_value, ev.value_type, ev.signal),
            currentValueLabel: fmtEvidenceValue(ev.current_value, ev.value_type, ev.signal),
            signalLabel: SIGNAL_LABEL[ev.signal] || ev.signal,
            observedLabel: fmtDate(ev.observed_at),
            sourceLabel: ev.source,
            reasonSummary: ev.evidence_summary || fmtEvidenceReason(candidate.reason_summary, ev.signal, ev.current_value),
          })),
        })),
        activityTimeline: raw.activities.map((act, i) => ({
          typeLabel: ACTIVITY_LABEL[act.activity_type] || act.activity_type,
          actorLabel: act.actor ? act.actor.display_name : 'System',
          occurredLabel: fmtDate(act.occurred_at),
          hasNote: !!act.note,
          note: act.note,
          hasLink: (act.external_links ?? []).length > 0,
          linkUrl: act.external_links?.[0]?.url ?? '',
          linkLabel: act.external_links?.[0]?.link_type === 'issue' ? '연결된 Issue' : '연결된 PR',
          rowStyle: (i === raw.activities.length - 1 && this.state.justAddedActivity) ? 'display:flex;gap:12px;padding:12px;margin:0 -12px;border-top:1px solid #F0F1EE;background:#E7F3EC;border-radius:8px' : 'display:flex;gap:12px;padding:12px 0;border-top:1px solid #F0F1EE',
        })),
      };
    }

    const actionButtons = selected ? [
      { label: '재검토 보류', style: 'font-size:12.5px;font-weight:600;font-family:inherit;color:#5B6058;background:#FFFFFF;border:1px solid #D2D5CD;border-radius:7px;padding:8px 14px;cursor:pointer', onClick: () => this.showPreviewNotice() },
      { label: '위험 수용', style: 'font-size:12.5px;font-weight:600;font-family:inherit;color:#5B6058;background:#FFFFFF;border:1px solid #D2D5CD;border-radius:7px;padding:8px 14px;cursor:pointer', onClick: () => this.showPreviewNotice() },
      selected.mergeMode === 'fully_auto' ? null :
      selected.mergeMode === 'click_to_merge'
        ? { label: 'PR 병합', style: 'font-size:12.5px;font-weight:600;font-family:inherit;color:#FFFFFF;background:#2F8F5B;border:none;border-radius:7px;padding:8px 14px;cursor:pointer', onClick: () => this.showPreviewNotice() }
        : selected.mergeMode === 'pr_only'
        ? { label: '업데이트 PR 생성', style: 'font-size:12.5px;font-weight:600;font-family:inherit;color:#FFFFFF;background:#2F8F5B;border:none;border-radius:7px;padding:8px 14px;cursor:pointer', onClick: () => this.showPrUnavailableNotice() }
        : { label: '조치 요청', style: 'font-size:12.5px;font-weight:600;font-family:inherit;color:#5B6058;background:#F5F6F3;border:1px solid #E4E6E1;border-radius:7px;padding:8px 14px;cursor:pointer', title: selected.automation.reason, onClick: () => this.showPreviewNotice() },
    ].filter(Boolean) : [];

    const formTitleMap = { review_deferred: '재검토 보류 기록', risk_accepted: '위험 수용 기록', remediation_requested: '조치 요청 기록' };

    return {
      isDashboardView: view === 'dashboard',
      isListView: view === 'list',
      isDetailView: view === 'detail',
      isReposView: view === 'repos',
      isSettingsView: view === 'settings',
      repoRows,
      hasRepositories: repoRows.length > 0,
      policyMatrixRows,
      importanceLevelOptions: importanceLevels.map(k => ({ value: k, label: PRIORITY_META[k].label })),
      modeSelectOptions: [
        { value: 'fully_auto', label: '완전 자동조치' },
        { value: 'click_to_merge', label: 'PR 병합 승인' },
        { value: 'pr_only', label: 'PR 생성만' },
      ],
      clearRepoFilter: () => this.setState(s => ({ filters: { ...s.filters, repo: 'all' } })),
      activeRepoFilterLabel: (() => {
        if (filters.repo === 'all') return null;
        const found = cases.find(c => c.repository.full_name === filters.repo);
        return found ? found.repository.display_name : null;
      })(),
      navTabs,
      kpiCards,
      topCases,
      hasDashboardCases: topCases.length > 0,
      flowStages,
      showSuppressedPopover: this.state.showSuppressedPopover || false,
      suppressedCases,
      closeSuppressedPopover: () => this.setState({ showSuppressedPopover: false }),
      weekRangeLabel: isDemo ? '8/18 ~ 8/24' : '현재 DB 기준',
      dashboardDescription: isDemo
        ? '지금 봐야 할 항목과 이번 주 위험 변화 흐름을 한눈에 확인하세요.'
        : '현재 DB에 저장된 재검토 현황을 확인하세요.',
      flowTitle: isDemo ? '이번 주 처리 흐름' : '전체 처리 흐름',
      goToDashboard: () => this.goToDashboard(),
      goToAllList: () => this.goToAllList(),
      filteredCases,
      isEmpty,
      hasResults: !isEmpty,
      resultCountLabel: `총 ${filteredCases.length}건 · 전체 열린 Case ${openTotal}건`,
      statusOptions,
      priorityChipOptions,
      changeTypeChipOptions,
      importanceChipOptions,
      staleToggle,
      filters,
      onPriorityChange: e => this.setPriorityFilter(e.target.value),
      onChangeTypeChange: e => this.setChangeTypeFilter(e.target.value),
      onSortChange: e => this.setSort(e.target.value),
      backToList: () => this.backToList(),
      selected,
      actionButtons,
      showPrUnavailableNotice: this.state.showPrUnavailableNotice,
      showActivityForm,
      activityFormTitle: formTitleMap[activityKind] || '',
      noteDraft,
      onNoteChange: e => this.setState({ noteDraft: e.target.value }),
      linkType,
      onLinkTypeChange: e => this.setState({ linkType: e.target.value }),
      linkUrl,
      onLinkUrlChange: e => this.setState({ linkUrl: e.target.value }),
      submitActivity: () => this.submitActivity(),
      cancelActivityForm: () => this.cancelActivityForm(),
      dataSource: this.props.dataSource,
      isDemo,
      onDataSourceChange: this.props.onDataSourceChange,
      isPreview: this.props.isPreview,
      showPreviewNotice: this.state.showPreviewNotice || false,
    };
  }

  render() {
    const values = this.renderVals();
    return (
      <div style={{ minHeight: '100vh', background: '#FAFBFA', fontFamily: "'Noto Sans KR',-apple-system,'Segoe UI',Helvetica,Arial,sans-serif", color: '#1B1E1A' }}>
        <Header values={values} />
        {this.props.loadState !== 'ready' ? (
          <ReviewDataState
            state={this.props.loadState}
            message={this.props.loadError}
            onRetry={this.props.onRetry}
          />
        ) : (
          <>
            <Dashboard values={values} />
            <Repositories values={values} />
            <Settings values={values} />
            <ReviewCaseList values={values} />
            <ReviewCaseDetail values={values} />
          </>
        )}
      </div>
    );
  }
}

export function WatchbackApp(props) {
  const router = useRouter();
  return <WatchbackAppView {...props} router={router} />;
}
