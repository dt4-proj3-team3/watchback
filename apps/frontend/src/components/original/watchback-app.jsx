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
  critical: { label: 'Critical', bg: '#FBEAE6', text: '#A6321B', border: '#E3B6AA', dot: '#C7402A' },
  high:     { label: 'High',     bg: '#FCEFE1', text: '#9A5A16', border: '#E9C99A', dot: '#C7752A' },
  medium:   { label: 'Medium',   bg: '#FBF3D9', text: '#8A6A05', border: '#E4D28C', dot: '#B08900' },
  low:      { label: 'Low',      bg: '#EEF0EE', text: '#5A6058', border: '#D2D5CD', dot: '#8B9086' },
};
const CHANGE_TYPE_LABEL = {
  kev_added: 'KEV 신규 등재',
  kev_new: 'KEV 신규 등재',
  epss_spike: 'EPSS 급등',
  epss_rise_d30: 'EPSS 급등',
  epss_top5_entry_d30: 'EPSS 상위 5% 진입',
  patch_available: '패치 버전 등장',
  combined_signal: '다중 신호 동시 변화',
};

function formatChangeType(value) {
  const normalized = String(value ?? '').trim().toLowerCase();
  return CHANGE_TYPE_LABEL[normalized] || value;
}
const SIGNAL_LABEL = {
  kev: 'CISA KEV 등재',
  epss: 'EPSS 점수',
  epss_score_d30: '향후 30일 악용 가능성',
  epss_percentile_d30: '전체 CVE 내 EPSS 순위',
  patch: '패치 버전',
  cvss: 'CVSS 점수',
  advisory_severity: '권고 심각도',
};
const ACTIVITY_LABEL = {
  case_reopened: 'Case 재오픈', case_resolved: 'Case 해결',
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

function fmtMonthDay(iso) {
  if (!iso) return '';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  return `${date.getUTCMonth() + 1}/${date.getUTCDate()}`;
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
    return `상위 ${((1 - number) * 100).toFixed(1).replace(/\.0$/, '')}%`;
  }
  if (signal === 'epss_score_d30') {
    const percent = number * 100;
    const digits = percent > 0 && percent < 0.1 ? 2 : 1;
    return `${percent.toFixed(digits).replace(/\.0+$/, '')}%`;
  }
  return number.toFixed(4).replace(/\.?0+$/, '');
}

function fmtEvidenceReason(reason, signal, previousValue, currentValue) {
  if (signal === 'kev' && previousValue === 'false' && currentValue === 'true') {
    return 'CISA에서 실제 악용 사례가 확인되었습니다.';
  }
  if (signal === 'epss_score_d30') {
    const previous = Number(previousValue);
    const current = Number(currentValue);
    if (Number.isFinite(previous) && Number.isFinite(current)) {
      const delta = (current - previous) * 100;
      return `30일 전보다 ${delta.toFixed(1).replace(/\.0$/, '')}%p 상승했습니다.`;
    }
  }
  if (signal === 'epss_percentile_d30') {
    const previous = Number(previousValue);
    const percentile = Number(currentValue);
    if (Number.isFinite(percentile)) {
      if (Number.isFinite(previous) && previous < 0.95 && percentile >= 0.95) {
        return '상위 5% 구간에 진입했습니다.';
      }
      return `전체 CVE 중 상위 ${((1 - percentile) * 100).toFixed(1).replace(/\.0$/, '')}%에 해당합니다.`;
    }
  }
  return String(reason ?? '').replace(/^\d{4}[-.]\d{2}[-.]\d{2}\s+/, '');
}

export function buildEvidenceGroups(candidates = []) {
  const groups = new Map();

  candidates.forEach((candidate) => {
    const changeType = String(candidate.change_type ?? '').trim().toLowerCase();
    let group = groups.get(changeType);
    if (!group) {
      group = {
        id: changeType,
        changeTypeLabel: formatChangeType(changeType),
        candidates: [],
        sourceAnnotations: [],
        evidence: [],
      };
      groups.set(changeType, group);
    }

    const sourceAnnotations = (candidate.deliveries ?? []).flatMap(
      delivery => delivery.source_annotations ?? [],
    );
    group.candidates.push(candidate);
    group.sourceAnnotations.push(...sourceAnnotations);
    group.evidence.push(...(candidate.evidence ?? []).map(ev => ({
      ...ev,
      candidateId: candidate.id,
      deliveries: candidate.deliveries ?? [],
      sourceAnnotations,
      previousValueLabel: fmtEvidenceValue(ev.previous_value, ev.value_type, ev.signal),
      currentValueLabel: fmtEvidenceValue(ev.current_value, ev.value_type, ev.signal),
      signalLabel: SIGNAL_LABEL[ev.signal] || ev.signal,
      observedLabel: fmtDate(ev.observed_at) === fmtDate(candidate.selected_at) ? null : fmtDate(ev.observed_at),
      reasonSummary: fmtEvidenceReason(
        ev.evidence_summary || candidate.reason_summary,
        ev.signal,
        ev.previous_value,
        ev.current_value,
      ),
    })));
  });

  return Array.from(groups.values()).map((group) => {
    const annotationKeys = new Set();
    const evidenceKeys = new Set();
    const sourceAnnotations = group.sourceAnnotations.filter((annotation) => {
      const key = `${annotation.snapshot_date}|${annotation.annotation_type}`;
      if (annotationKeys.has(key)) return false;
      annotationKeys.add(key);
      return true;
    });
    const evidence = group.evidence
      .filter((item) => {
        const key = [
          item.signal,
          item.observed_at,
          item.previous_value,
          item.current_value,
          item.source,
        ].join('|');
        if (evidenceKeys.has(key)) return false;
        evidenceKeys.add(key);
        return true;
      })
      .sort((left, right) => (
        new Date(left.observed_at) - new Date(right.observed_at) ||
        String(left.id).localeCompare(String(right.id))
      ));
    const firstObservedAt = evidence[0]?.observed_at ?? group.candidates[0]?.selected_at;
    return {
      ...group,
      selectedLabel: group.candidates.length === 1
        ? fmtDate(group.candidates[0].selected_at)
        : null,
      sourceAnnotations,
      evidence,
      firstObservedAt,
    };
  }).sort((left, right) => (
    new Date(left.firstObservedAt) - new Date(right.firstObservedAt) ||
    left.id.localeCompare(right.id)
  ));
}

function formatReviewReason(reason) {
  const match = reason.match(/^(\d{4})-(\d{2})-(\d{2})\s+(.+)$/);
  const simplify = (text) => text.replace('EPSS D-30 급상승 조건', 'EPSS 급상승 조건');
  if (!match) return { dateLabel: null, text: simplify(reason) };
  return { dateLabel: `${match[1]}.${match[2]}.${match[3]}`, text: simplify(match[4]) };
}

function badgeStyle(meta) {
  return `font-size:11px;font-weight:600;color:${meta.text};background:${meta.bg};border-radius:20px;padding:3px 9px;white-space:nowrap`;
}

function formatWeeklyTrend(delta) {
  if (delta === 0) return '지난주 대비 변화 없음';
  return `지난주 대비 ${delta > 0 ? '▲' : '▼'}${Math.abs(delta)}건`;
}

const KEV_BADGE = { label: 'KEV', style: 'font-size:11px;font-weight:600;color:#A6321B;background:#FBEAE6;border-radius:5px;padding:2px 7px;white-space:nowrap' };

function evidenceTags(evidence = [], isKev = false) {
  const hasKevAdded = isKev || evidence.some(item => item.signal === 'kev' && item.current_value === 'true');
  const hasEpssSpike = evidence.some(item => item.signal === 'epss_score_d30' && Number(item.current_value) > Number(item.previous_value));
  const hasTopFiveEntry = evidence.some(item => (
    item.signal === 'epss_percentile_d30' &&
    Number(item.previous_value) < 0.95 &&
    Number(item.current_value) >= 0.95
  ));

  const tags = [];
  if (hasKevAdded) {
    tags.push(KEV_BADGE);
  }
  if (hasEpssSpike) {
    tags.push({ label: 'EPSS 급등', style: 'font-size:11px;font-weight:600;color:#2F8F5B;background:#E7F3EC;border-radius:5px;padding:2px 7px;white-space:nowrap' });
  }
  if (tags.length < 2 && hasTopFiveEntry) {
    tags.push({ label: '상위 5%', style: 'font-size:11px;font-weight:600;color:#1F6FBF;background:#E6EFFA;border-radius:5px;padding:2px 7px;white-space:nowrap' });
  }
  return tags.slice(0, 2);
}

function latestCandidateTags(candidate, isKev = false) {
  if (!candidate) return [];
  const labels = {
    epss_spike: 'EPSS 급등',
    epss_rise_d30: 'EPSS 급등',
    epss_top5_entry_d30: '상위 5%',
    patch_available: '패치 등장',
    combined_signal: '다중 신호',
  };
  const changeType = String(candidate.change_type ?? '').toLowerCase();
  const tags = isKev || changeType === 'kev_added' || changeType === 'kev_new'
    ? [KEV_BADGE]
    : [];
  const label = labels[changeType];
  if (label) {
    tags.push({ label, style: 'font-size:11px;font-weight:600;color:#2F8F5B;background:#E7F3EC;border-radius:5px;padding:2px 7px;white-space:nowrap' });
  }
  return tags.slice(0, 2);
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
    activityError: '',
    isSubmittingActivity: false,
    justAddedActivity: false,
    showActionMenu: false,
    actionNotice: '',
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
        showActionMenu: false,
      });
    }
  }

  componentWillUnmount() {
    clearTimeout(this.previewNoticeTimer);
  }

  enrich(c) {
    const pm = PRIORITY_META[c.priority];
    const im = PRIORITY_META[c.repository.importance];
    const sm = PRIORITY_META[c.advisory.severity];
    const reviewReason = formatReviewReason(c.review_reason);
    const detailedEvidenceTags = evidenceTags(c.evidence, c.is_kev);
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
      changeTypeLabel: formatChangeType(c.latest_candidate.change_type),
      evidenceTags: detailedEvidenceTags.length > 0
        ? detailedEvidenceTags
        : latestCandidateTags(c.latest_candidate, c.is_kev),
      hasSourceAnnotation: (c.source_annotations ?? []).length > 0,
      reviewReasonLabel: reviewReason.text,
      reviewReasonDateLabel: reviewReason.dateLabel,
      isResolved: c.status === 'resolved',
      isReopened: c.reopened_count > 0,
      openedLabel: fmtDate(c.opened_at),
      updatedLabel: fmtDate(c.updated_at),
      hasDistinctUpdatedDate: fmtDate(c.opened_at) !== fmtDate(c.updated_at),
      onOpen: () => this.openCase(c.id),
    };
  }

  openCase(id) {
    this.props.router.push(`/review-cases/${id}`);
  }

  backToPrevious() {
    this.props.router.back();
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
  openActivityForm(kind) {
    this.setState({
      showActivityForm: true,
      showActionMenu: false,
      actionNotice: '',
      activityKind: kind,
      noteDraft: '',
      linkType: '',
      linkUrl: '',
      activityError: '',
      justAddedActivity: false,
    });
  }
  cancelActivityForm() {
    if (this.state.isSubmittingActivity) return;
    this.setState({ showActivityForm: false, activityKind: null, activityError: '' });
  }

  openActionMenu() {
    this.setState({ showActionMenu: true, showActivityForm: false, actionNotice: '' });
  }

  closeActionMenu() {
    this.setState({ showActionMenu: false, actionNotice: '' });
  }

  showActionUnavailable(kind) {
    const message = kind === 'issue'
      ? 'GitHub Issue 생성 API는 아직 구현되지 않았습니다.'
      : '업데이트 PR 생성 API는 아직 구현되지 않았습니다.';
    this.setState({ actionNotice: message });
  }

  showPreviewNotice() {
    this.setState({ showPreviewNotice: true, showActivityForm: false });
    clearTimeout(this.previewNoticeTimer);
    this.previewNoticeTimer = setTimeout(() => this.setState({ showPreviewNotice: false }), 3000);
  }

  async submitActivity() {
    if (this.state.isSubmittingActivity) return;
    const selected = this.props.initialCases.find(c => c.id === this.state.selectedId);
    const candidateId = selected?.latest_candidate?.id;
    if (!selected || !candidateId) {
      this.setState({ activityError: '연결할 최신 위험 후보를 찾을 수 없습니다.' });
      return;
    }

    const activityType = this.state.activityKind;
    const note = this.state.noteDraft.trim();
    const linkType = this.state.linkType;
    const linkUrl = this.state.linkUrl.trim();
    const requiresNote = activityType !== 'external_link_added';
    if (requiresNote && !note) {
      this.setState({ activityError: '활동 메모를 입력해 주세요.' });
      return;
    }
    if (activityType === 'external_link_added' && (!linkType || !linkUrl)) {
      this.setState({ activityError: '연결할 GitHub Issue 또는 PR을 입력해 주세요.' });
      return;
    }
    if ((linkType && !linkUrl) || (!linkType && linkUrl)) {
      this.setState({ activityError: '외부 링크 유형과 URL을 함께 입력해 주세요.' });
      return;
    }
    if (linkUrl) {
      const expected = linkType === 'issue' ? 'issues' : 'pull';
      const pattern = new RegExp(`^https://github\\.com/[^/]+/[^/]+/${expected}/\\d+/?$`);
      if (!pattern.test(linkUrl)) {
        this.setState({ activityError: '선택한 유형과 일치하는 GitHub Issue 또는 PR URL을 입력해 주세요.' });
        return;
      }
    }

    const payload = { activity_type: activityType, candidate_id: candidateId };
    if (note) payload.note = note;
    if (linkUrl) payload.external_link = { link_type: linkType, url: linkUrl };

    this.setState({ isSubmittingActivity: true, activityError: '' });
    try {
      await this.props.onCreateActivity(selected.id, payload);
      this.setState({
        showActivityForm: false,
        activityKind: null,
        noteDraft: '',
        linkType: '',
        linkUrl: '',
        isSubmittingActivity: false,
        justAddedActivity: true,
      });
    } catch (error) {
      const messages = {
        duplicate_activity: '현재 후보에 같은 활동이 이미 기록되어 있습니다.',
        duplicate_external_link: '이미 연결된 GitHub Issue 또는 PR입니다.',
        organization_scope_violation: '이 조직의 Case에 활동을 기록할 권한이 없습니다.',
        review_case_not_found: '재검토 Case를 찾을 수 없습니다.',
        candidate_not_found: '현재 후보를 이 Case에서 찾을 수 없습니다.',
        backend_unavailable: 'Backend에 연결할 수 없습니다.',
      };
      this.setState({
        isSubmittingActivity: false,
        activityError: messages[error?.code] || error?.message || '활동을 기록하지 못했습니다.',
      });
    }
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
        const dashboardEvidenceTags = e.evidenceTags.map(tag => ({
          ...tag,
          label: tag.label === '상위 5%' ? 'EPSS 상위 5%' : tag.label,
        }));
        const daysOpen = Math.floor((Date.now() - new Date(c.opened_at)) / 86400000);
        const urgencyLabel = c.reopened_count > 0 ? `재오픈 ${c.reopened_count}회` : (daysOpen >= 3 ? `${daysOpen}일째 미처리` : null);
        const patchLabel = c.latest_candidate.change_type === 'patch_available' && c.alert.first_patched_version ? `패치 ${c.alert.first_patched_version}` : null;
        return { ...e, evidenceTags: dashboardEvidenceTags, urgencyLabel, patchLabel };
      });

    const criticalOpenCount = cases.filter(c => c.status === 'open' && c.repository.importance === 'critical').length;
    const staleCount = cases.filter(c => c.status === 'open' && (Date.now() - new Date(c.opened_at)) / 86400000 >= 3).length;
    const sourceImpactCases = cases.filter(c => (
      c.status === 'open' && (c.source_annotations ?? []).length > 0
    ));
    const trendReference = isDemo ? Date.parse('2026-08-25T00:00:00Z') : Date.now();
    const currentWeekStart = trendReference - (7 * 86400000);
    const previousWeekStart = trendReference - (14 * 86400000);
    const currentWeekSourceImpactCount = sourceImpactCases.filter(c => {
      const openedAt = new Date(c.opened_at).getTime();
      return openedAt >= currentWeekStart && openedAt < trendReference;
    }).length;
    const previousWeekSourceImpactCount = sourceImpactCases.filter(c => {
      const openedAt = new Date(c.opened_at).getTime();
      return openedAt >= previousWeekStart && openedAt < currentWeekStart;
    }).length;
    const sourceImpactDelta = currentWeekSourceImpactCount - previousWeekSourceImpactCount;
    const dashboardSummary = this.props.dashboardSummary;
    const criticalMetric = dashboardSummary?.critical_open;
    const staleMetric = dashboardSummary?.stale_open;
    const sourceMetric = dashboardSummary?.source_impact_open;
    const sourceImpactTrend = formatWeeklyTrend(
      isDemo ? sourceImpactDelta : (sourceMetric?.delta ?? 0),
    );
    const dashboardPeriodLabel = isDemo
      ? '8/18 ~ 8/24'
      : [
        fmtMonthDay(dashboardSummary?.previous_reference_at),
        fmtMonthDay(dashboardSummary?.reference_at),
      ].filter(Boolean).join(' ~ ');

    const kpiCards = [
      { label: 'Critical 저장소 미처리', value: `${isDemo ? criticalOpenCount : (criticalMetric?.current_count ?? criticalOpenCount)}건`, hint: '가장 중요한 저장소에 열려있는 항목', trend: formatWeeklyTrend(isDemo ? 1 : (criticalMetric?.delta ?? 0)), cursorStyle: 'pointer', onClick: () => this.goToFilteredList({ ...filters, status: 'open', importance: 'critical', staleOnly: false }) },
      { label: '3일 이상 미처리', value: `${isDemo ? staleCount : (staleMetric?.current_count ?? staleCount)}건`, hint: '재검토 대상이 된 지 오래된 항목', trend: formatWeeklyTrend(isDemo ? 0 : (staleMetric?.delta ?? 0)), cursorStyle: 'pointer', onClick: () => this.goToFilteredList({ ...filters, status: 'open', importance: 'all', staleOnly: true, sort: 'opened_at' }) },
      { label: '소스 변동 영향 추정', value: `${isDemo ? sourceImpactCases.length : (sourceMetric?.current_count ?? sourceImpactCases.length)}건`, hint: 'EPSS 모델·소스 변동일과 겹친 재검토 항목', trend: sourceImpactTrend, cursorStyle: sourceImpactCases.length > 0 ? 'pointer' : 'default', onClick: sourceImpactCases.length > 0 ? () => this.setState({ showSuppressedPopover: true }) : undefined },
    ];

    const flowStages = [
      { label: '열림', count: openTotal - inProgressTotal, hasArrow: true, onClick: () => this.goToFilteredList({ ...filters, status: 'open', importance: 'all', staleOnly: false }) },
      { label: '조치 요청됨', count: inProgressTotal, hasArrow: true, onClick: () => this.goToFilteredList({ ...filters, status: 'open', importance: 'all', staleOnly: false }) },
      { label: '해결됨', count: resolvedTotal, hasArrow: false, onClick: () => this.goToFilteredList({ ...filters, status: 'resolved', importance: 'all', staleOnly: false }) },
    ].map(s => ({ ...s, containerStyle: 'display:flex;align-items:center;flex:none' }));

    const suppressedCases = sourceImpactCases.map(c => ({
      repoName: c.repository.display_name,
      reason: (c.source_annotations ?? [])
        .map(annotation => `${annotation.snapshot_date.replaceAll('-', '.')} · ${annotation.label}`)
        .join(', '),
    }));

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
      const reviewActivities = raw.activities.filter(
        activity => activity.activity_type !== 'case_opened',
      );
      const e = this.enrich(raw);
      const relatedAlerts = raw.alerts?.length ? raw.alerts : [raw.alert];
      const sourceAnnotations = raw.candidates.flatMap(candidate => (
        (candidate.deliveries ?? []).flatMap(delivery => delivery.source_annotations ?? [])
      ));
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
        systemicLabel: sourceAnnotations.length > 0 ? '소스 변동 주의' : '개별 변화로 확인됨',
        systemicColor: sourceAnnotations.length > 0 ? '#9A5A16' : '#2F8F5B',
        systemicBg: sourceAnnotations.length > 0 ? '#FCEFE1' : '#E7F3EC',
        automationStatusLabel: { fully_auto: '완전 자동조치 (미구현)', click_to_merge: 'PR 병합 대기 (미구현)', pr_only: 'PR 생성 대상 (미구현)' }[configuredMergeMode] || '자동조치 미구현',
        automationStatusColor: automation.eligible ? '#2F8F5B' : '#8B9086',
        automationStatusBg: automation.eligible ? '#E7F3EC' : '#EEF0EE',
        hasPr: !!automation.prUrl,
        mergeMode: configuredMergeMode,
        patchLabelShort: raw.alert.first_patched_version || '패치 없음',
        patchColor: raw.alert.first_patched_version ? '#2F8F5B' : '#8B9086',
        relatedAlerts,
        manifestLabel: relatedAlerts
          .map(alert => alert.manifest_path)
          .filter(Boolean)
          .join(', ') || '-',
        evidenceGroups: buildEvidenceGroups(raw.candidates),
        activityTimeline: reviewActivities.map((act, i) => ({
          typeLabel: ACTIVITY_LABEL[act.activity_type] || act.activity_type,
          actorLabel: act.actor ? act.actor.display_name : 'System',
          occurredLabel: fmtDate(act.occurred_at),
          hasNote: !!act.note,
          note: act.note,
          hasLink: (act.external_links ?? []).length > 0,
          linkUrl: act.external_links?.[0]?.url ?? '',
          linkLabel: act.external_links?.[0]?.link_type === 'issue' ? '연결된 Issue' : '연결된 PR',
          rowStyle: (i === reviewActivities.length - 1 && this.state.justAddedActivity) ? 'display:flex;gap:12px;padding:12px;margin:0 -12px;border-top:1px solid #F0F1EE;background:#E7F3EC;border-radius:8px' : 'display:flex;gap:12px;padding:12px 0;border-top:1px solid #F0F1EE',
        })),
      };
    }

    const actionButtons = selected ? [
      { label: '위험 수용', style: 'font-size:12.5px;font-weight:600;font-family:inherit;color:#5B6058;background:#FFFFFF;border:1px solid #D2D5CD;border-radius:7px;padding:8px 14px;cursor:pointer', onClick: () => this.openActivityForm('risk_accepted') },
      { label: '조치하기', style: 'font-size:12.5px;font-weight:600;font-family:inherit;color:#FFFFFF;background:#2F8F5B;border:none;border-radius:7px;padding:8px 14px;cursor:pointer', onClick: () => this.openActionMenu() },
    ] : [];

    const formTitleMap = {
      risk_accepted: '위험 수용 기록',
    };

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
      weekRangeLabel: dashboardPeriodLabel,
      dashboardDescription: '지금 봐야 할 항목과 이번 주 위험 변화 흐름을 한눈에 확인하세요.',
      flowTitle: '이번 주 처리 흐름',
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
      backToPrevious: () => this.backToPrevious(),
      selected,
      actionButtons,
      showActionMenu: this.state.showActionMenu,
      closeActionMenu: () => this.closeActionMenu(),
      createIssue: () => this.showActionUnavailable('issue'),
      createPullRequest: () => this.showActionUnavailable('pull_request'),
      actionNotice: this.state.actionNotice,
      showActivityForm,
      activityFormTitle: formTitleMap[activityKind] || '',
      activityKind,
      noteDraft,
      onNoteChange: e => this.setState({ noteDraft: e.target.value }),
      linkType,
      onLinkTypeChange: e => this.setState({ linkType: e.target.value }),
      linkUrl,
      onLinkUrlChange: e => this.setState({ linkUrl: e.target.value }),
      submitActivity: () => this.submitActivity(),
      cancelActivityForm: () => this.cancelActivityForm(),
      activityError: this.state.activityError,
      isSubmittingActivity: this.state.isSubmittingActivity,
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
