from __future__ import annotations

import re
import os
import time
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import PurePosixPath
from uuid import UUID, uuid4

from packaging.version import InvalidVersion, Version
from sqlalchemy import exists, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from watchback_backend.api.normalization import (
    normalize_change_type,
    normalize_evidence_signal,
)
from watchback_backend.api.schemas import (
    CandidateDelivery,
    CandidateDetail,
    EvidenceResponse,
    SourceAnnotation,
)
from watchback_backend.api.source_annotations import annotations_for_observed_at
from watchback_backend.api.service import RequestContext, ServiceError
from watchback_backend.db.models import (
    AlertCandidateMatch,
    CandidateEvidence,
    DependencyVersionSnapshot,
    DependabotAlert,
    GoldBatch,
    GoldBatchCandidate,
    Repository,
    RemediationAction,
    RemediationActionTarget,
    RemediationAISummary,
    ReviewCase,
    RiskCandidate,
    SecurityAdvisory,
    User,
)
from watchback_backend.remediation.schemas import (
    GitHubAlertCounts,
    RemediationActionCreate,
    RemediationActionCreated,
    RemediationActionTargetResponse,
    RemediationActionType,
    RemediationReopened,
    RemediationAISummaryResponse,
    RemediationAlert,
    RemediationGroup,
    RemediationGroupListResponse,
    RemediationHistoryItem,
    RemediationPullRequest,
    RemediationAlertVerification,
    RemediationPullRequestBatchCreated,
    RemediationPullRequestCreate,
    RemediationPullRequestCloseResponse,
    RemediationPullRequestMergeRequest,
    RemediationPullRequestMergeResponse,
    RemediationRepository,
    RemediationTarget,
    RemediationVulnerability,
    WatchbackActionState,
    WatchbackGroupStatus,
)


PRIORITY_RANK = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
ALERT_STATES = ("open", "fixed", "dismissed", "auto_dismissed")
DEPENDENCY_CONTEXT_FILES = {
    "cargo.lock",
    "cargo.toml",
    "composer.json",
    "composer.lock",
    "gemfile",
    "gemfile.lock",
    "package-lock.json",
    "package.json",
    "pipfile",
    "pipfile.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "pyproject.toml",
    "uv.lock",
    "yarn.lock",
}


@dataclass(frozen=True)
class RemediationSourceRow:
    organization_id: UUID
    case_id: UUID
    case_status: str
    case_opened_at: datetime
    repository_id: UUID
    repository_full_name: str
    repository_display_name: str
    repository_importance: str
    alert_id: UUID
    github_alert_number: int
    alert_state: str
    package_name: str
    ecosystem: str
    manifest_path: str | None
    vulnerable_version_range: str
    first_patched_version: str | None
    alert_html_url: str
    alert_github_updated_at: datetime
    ghsa_id: str
    cve_id: str
    advisory_summary: str
    advisory_severity: str
    candidate_id: UUID
    candidate_priority: str
    candidate_change_type: str
    candidate_selected_at: datetime
    candidate_reason_summary: str = ""
    dependency_scope: str | None = None
    dependency_relationship: str | None = None


def _stable_id(*parts: object) -> str:
    raw = "\x1f".join("" if part is None else str(part) for part in parts)
    return sha256(raw.encode("utf-8")).hexdigest()


def _canonical_package_name(ecosystem: str, package_name: str) -> str:
    normalized_ecosystem = ecosystem.lower()
    if normalized_ecosystem == "pip":
        return re.sub(r"[-_.]+", "-", package_name).lower()
    if normalized_ecosystem == "npm":
        return package_name.lower()
    return package_name


def _dependency_project_root(manifest_path: str | None) -> str:
    if not manifest_path:
        return ""
    path = PurePosixPath(manifest_path)
    if path.name.lower() not in DEPENDENCY_CONTEXT_FILES:
        return manifest_path
    parent = str(path.parent)
    return "" if parent == "." else parent


def _target_id(row: RemediationSourceRow) -> str:
    return _stable_id(
        row.repository_id,
        row.ecosystem,
        _dependency_project_root(row.manifest_path),
    )


def _is_supported_remediation_dependency(row: RemediationSourceRow) -> bool:
    if row.dependency_scope != "runtime":
        return False
    if row.dependency_relationship == "direct":
        return True
    return (
        row.ecosystem.lower() == "pip"
        and row.dependency_relationship == "unknown"
        and PurePosixPath(row.manifest_path or "").name.lower() == "pyproject.toml"
    )


def _watchback_status(statuses: set[str]) -> WatchbackGroupStatus:
    if "open" in statuses or not statuses:
        return WatchbackGroupStatus.NEEDS_REVIEW
    if "accepted" in statuses:
        return WatchbackGroupStatus.ACCEPTED
    return WatchbackGroupStatus.RESOLVED


def _alert_counts(states: list[str]) -> GitHubAlertCounts:
    counts = {state: 0 for state in ALERT_STATES}
    for state in states:
        if state in counts:
            counts[state] += 1
    return GitHubAlertCounts(**counts)


def _load_source_rows(
    session: Session, context: RequestContext
) -> list[RemediationSourceRow]:
    representative_alert = aliased(DependabotAlert)
    representative_advisory = aliased(SecurityAdvisory)
    related_alert = aliased(DependabotAlert)
    related_advisory = aliased(SecurityAdvisory)

    has_candidate_match = exists(
        select(AlertCandidateMatch.alert_id).where(
            AlertCandidateMatch.organization_id == context.organization_id,
            AlertCandidateMatch.alert_id == related_alert.id,
        )
    )
    rows = session.execute(
        select(
            ReviewCase.organization_id,
            ReviewCase.id.label("case_id"),
            ReviewCase.status.label("case_status"),
            ReviewCase.opened_at.label("case_opened_at"),
            Repository.id.label("repository_id"),
            Repository.full_name.label("repository_full_name"),
            Repository.display_name.label("repository_display_name"),
            Repository.importance.label("repository_importance"),
            related_alert.id.label("alert_id"),
            related_alert.github_alert_number,
            related_alert.state.label("alert_state"),
            related_alert.package_name,
            related_alert.ecosystem,
            related_alert.manifest_path,
            related_alert.vulnerable_version_range,
            related_alert.first_patched_version,
            related_alert.dependency_scope,
            related_alert.dependency_relationship,
            related_alert.html_url.label("alert_html_url"),
            related_alert.github_updated_at.label("alert_github_updated_at"),
            related_advisory.ghsa_id,
            related_advisory.cve_id,
            related_advisory.summary.label("advisory_summary"),
            related_advisory.severity.label("advisory_severity"),
            RiskCandidate.id.label("candidate_id"),
            RiskCandidate.priority.label("candidate_priority"),
            RiskCandidate.change_type.label("candidate_change_type"),
            RiskCandidate.reason_summary.label("candidate_reason_summary"),
            RiskCandidate.selected_at.label("candidate_selected_at"),
        )
        .join(
            representative_alert,
            representative_alert.id == ReviewCase.alert_id,
        )
        .join(
            representative_advisory,
            representative_advisory.id == representative_alert.advisory_id,
        )
        .join(Repository, Repository.id == representative_alert.repository_id)
        .join(
            related_alert,
            (related_alert.organization_id == ReviewCase.organization_id)
            & (related_alert.repository_id == representative_alert.repository_id),
        )
        .join(related_advisory, related_advisory.id == related_alert.advisory_id)
        .join(
            RiskCandidate,
            RiskCandidate.id == ReviewCase.representative_candidate_id,
        )
        .where(
            ReviewCase.organization_id == context.organization_id,
            representative_advisory.cve_id.is_not(None),
            related_advisory.cve_id == representative_advisory.cve_id,
            has_candidate_match,
        )
        .order_by(
            related_alert.ecosystem.asc(),
            related_alert.package_name.asc(),
            Repository.full_name.asc(),
            related_alert.manifest_path.asc().nulls_first(),
            related_alert.github_alert_number.asc(),
        )
    ).mappings()
    return [RemediationSourceRow(**row) for row in rows]


def build_remediation_groups(
    rows: list[RemediationSourceRow],
    *,
    versions_by_target: dict[tuple[UUID, str | None, str, str], DependencyVersionSnapshot] | None = None,
    details_by_candidate: dict[UUID, CandidateDetail] | None = None,
    accepted_target_keys: set[tuple[UUID, UUID]] | None = None,
) -> RemediationGroupListResponse:
    versions_by_target = versions_by_target or {}
    details_by_candidate = details_by_candidate or {}
    accepted_target_keys = accepted_target_keys or set()
    grouped: dict[tuple[UUID, str, str], list[RemediationSourceRow]] = defaultdict(list)
    for row in rows:
        grouped[
            (
                row.organization_id,
                row.ecosystem,
                _canonical_package_name(row.ecosystem, row.package_name),
            )
        ].append(row)

    groups: list[RemediationGroup] = []
    for (organization_id, ecosystem, package_name), group_rows in grouped.items():
        alerts_by_id = {row.alert_id: row for row in group_rows}
        cases_by_id = {row.case_id: row for row in group_rows}
        open_case_ids = {
            row.case_id for row in group_rows if row.alert_state == "open"
        }
        priority_rows = (
            [row for case_id, row in cases_by_id.items() if case_id in open_case_ids]
            or list(cases_by_id.values())
        )
        priorities = sorted(
            {row.candidate_priority for row in priority_rows},
            key=lambda value: PRIORITY_RANK.get(value, 99),
        )
        target_rows: dict[tuple[UUID, str], list[RemediationSourceRow]] = (
            defaultdict(list)
        )
        for row in group_rows:
            target_rows[
                (row.repository_id, _dependency_project_root(row.manifest_path))
            ].append(row)

        targets: list[RemediationTarget] = []
        for (repository_id, project_root), rows_for_target in target_rows.items():
            target_alerts = {row.alert_id: row for row in rows_for_target}
            target_cases = {row.case_id: row for row in rows_for_target}
            repository_row = rows_for_target[0]
            manifest_paths = sorted(
                {
                    row.manifest_path
                    for row in rows_for_target
                    if row.manifest_path is not None
                }
            )
            target_fix_versions = sorted(
                {
                    row.first_patched_version
                    for row in target_alerts.values()
                    if row.first_patched_version
                }
            )
            version_snapshots = [
                snapshot
                for manifest_path in manifest_paths
                if (
                    snapshot := versions_by_target.get(
                        (
                            repository_id,
                            manifest_path,
                            repository_row.ecosystem,
                            _canonical_package_name(
                                repository_row.ecosystem,
                                repository_row.package_name,
                            ),
                        )
                    )
                )
                is not None
            ]
            has_open_alert = any(
                row.alert_state == "open" for row in target_alerts.values()
            )
            manifest_was_removed = bool(version_snapshots) and all(
                snapshot.status == "unavailable"
                and snapshot.reason == "lockfile_not_found"
                for snapshot in version_snapshots
            )
            if not has_open_alert and manifest_was_removed:
                continue
            current_versions = sorted(
                {
                    version
                    for snapshot in version_snapshots
                    for version in snapshot.resolved_versions
                }
            )
            targets.append(
                RemediationTarget(
                    id=_target_id(repository_row),
                    repository=RemediationRepository(
                        id=repository_id,
                        full_name=repository_row.repository_full_name,
                        display_name=repository_row.repository_display_name,
                        importance=repository_row.repository_importance,
                    ),
                    project_root=project_root,
                    manifest_paths=manifest_paths,
                    manifest_path=manifest_paths[0] if manifest_paths else None,
                    watchback_status=_rows_watchback_status(
                        list(target_alerts.values()), accepted_target_keys
                    ),
                    github_alert_counts=_alert_counts(
                        [row.alert_state for row in target_alerts.values()]
                    ),
                    case_ids=sorted(target_cases, key=str),
                    alerts=[
                        _alert_from_row(row)
                        for row in sorted(
                            target_alerts.values(),
                            key=lambda item: item.github_alert_number,
                        )
                    ],
                    recommended_fix_versions=target_fix_versions,
                    representative_patched_version=_highest_version(
                        target_fix_versions
                    ),
                    current_versions=current_versions,
                    current_version_status=(
                        "resolved"
                        if len(current_versions) == 1
                        else "multiple"
                        if current_versions
                        else version_snapshots[0].status
                        if version_snapshots
                        else "unavailable"
                    ),
                    current_version_reason=(
                        None
                        if current_versions
                        else version_snapshots[0].reason
                        if version_snapshots
                        else "not_collected"
                    ),
                )
            )

        rows_by_cve: dict[str, list[RemediationSourceRow]] = defaultdict(list)
        for row in group_rows:
            rows_by_cve[row.cve_id].append(row)
        vulnerabilities: list[RemediationVulnerability] = []
        for cve_id, cve_rows in rows_by_cve.items():
            cve_cases = {row.case_id: row for row in cve_rows}
            representative = min(
                cve_cases.values(),
                key=lambda item: (
                    PRIORITY_RANK.get(item.candidate_priority, 99),
                    -item.candidate_selected_at.timestamp(),
                    str(item.candidate_id),
                ),
            )
            representative_detail = details_by_candidate.get(
                representative.candidate_id
            )
            candidate_history = sorted(
                (
                    detail
                    for detail in details_by_candidate.values()
                    if detail.cve_id == cve_id
                ),
                key=lambda detail: (detail.selected_at, str(detail.id)),
            )
            vulnerabilities.append(
                RemediationVulnerability(
                    cve_id=cve_id,
                    ghsa_id=representative.ghsa_id,
                    advisory_summary=representative.advisory_summary,
                    advisory_severity=representative.advisory_severity,
                    priority=representative.candidate_priority,
                    candidate_id=representative.candidate_id,
                    change_type=normalize_change_type(
                        representative.candidate_change_type
                    ),
                    reason_summary=(
                        representative.candidate_reason_summary
                        or representative.advisory_summary
                    ),
                    selected_at=representative.candidate_selected_at,
                    watchback_status=_rows_watchback_status(
                        list({row.alert_id: row for row in cve_rows}.values()),
                        accepted_target_keys,
                    ),
                    case_ids=sorted(cve_cases, key=str),
                    alert_ids=sorted(
                        {row.alert_id for row in cve_rows},
                        key=str,
                    ),
                    evidence=(representative_detail.evidence if representative_detail else []),
                    deliveries=(representative_detail.deliveries if representative_detail else []),
                    candidates=candidate_history,
                )
            )
        vulnerabilities.sort(
            key=lambda item: (
                PRIORITY_RANK.get(item.priority.value, 99),
                item.cve_id,
            )
        )
        unique_fix_versions = sorted(
            {
                row.first_patched_version
                for row in alerts_by_id.values()
                if row.first_patched_version
            }
        )
        groups.append(
            RemediationGroup(
                id=_stable_id(organization_id, ecosystem, package_name),
                organization_id=organization_id,
                ecosystem=ecosystem,
                package_name=package_name,
                priority=priorities[0] if priorities else "P3",
                watchback_status=_rows_watchback_status(
                    list(alerts_by_id.values()), accepted_target_keys
                ),
                github_alert_counts=_alert_counts(
                    [row.alert_state for row in alerts_by_id.values()]
                ),
                cve_count=len(rows_by_cve),
                repository_count=len(
                    {row.repository_id for row in alerts_by_id.values()}
                ),
                recommended_fix_versions=unique_fix_versions,
                representative_patched_version=_highest_version(
                    unique_fix_versions
                ),
                registered_at=min(row.case_opened_at for row in cases_by_id.values()),
                updated_at=max(
                    row.alert_github_updated_at for row in alerts_by_id.values()
                ),
                targets=sorted(
                    targets,
                    key=lambda target: (
                        target.repository.full_name,
                        target.project_root,
                    ),
                ),
                vulnerabilities=vulnerabilities,
            )
        )

    groups.sort(
        key=lambda group: (
            PRIORITY_RANK.get(group.priority.value, 99),
            group.package_name,
            group.ecosystem,
        )
    )
    return RemediationGroupListResponse(items=groups, total=len(groups))


def _highest_version(versions: list[str]) -> str | None:
    parsed: list[tuple[Version, str]] = []
    for value in versions:
        try:
            parsed.append((Version(value), value))
        except InvalidVersion:
            return versions[0] if len(versions) == 1 else None
    return max(parsed, key=lambda item: item[0])[1] if parsed else None


def _rows_watchback_status(
    rows: list[RemediationSourceRow],
    accepted_target_keys: set[tuple[UUID, UUID]],
) -> WatchbackGroupStatus:
    return _watchback_status(
        {
            (
                "resolved"
                if row.alert_state != "open"
                else "accepted"
                if (row.alert_id, row.candidate_id) in accepted_target_keys
                else "open"
            )
            for row in rows
        }
    )


def _alert_from_row(row: RemediationSourceRow) -> RemediationAlert:
    return RemediationAlert(
        id=row.alert_id,
        github_alert_number=row.github_alert_number,
        state=row.alert_state,
        cve_id=row.cve_id,
        ghsa_id=row.ghsa_id,
        vulnerable_version_range=row.vulnerable_version_range,
        first_patched_version=row.first_patched_version,
        html_url=row.alert_html_url,
        github_updated_at=row.alert_github_updated_at,
    )


def list_remediation_groups(
    session: Session, context: RequestContext
) -> RemediationGroupListResponse:
    rows = _load_source_rows(session, context)
    result = build_remediation_groups(
        rows,
        versions_by_target=_load_current_versions(session, context),
        details_by_candidate=_load_candidate_details(
            session, {row.alert_id for row in rows}
        ),
        accepted_target_keys=_load_accepted_target_keys(session, context),
    )
    summaries = {
        item.group_key: item
        for item in session.scalars(
            select(RemediationAISummary).where(
                RemediationAISummary.organization_id == context.organization_id
            )
        ).all()
    }
    action_history = _load_action_history_by_group(session, context)
    return RemediationGroupListResponse(
        items=[
            group.model_copy(
                update={
                    "ai_summary": (
                        RemediationAISummaryResponse.model_validate(summary)
                        if (summary := summaries.get(group.id)) is not None
                        else None
                    ),
                    "action_history": action_history.get(group.id, []),
                }
            )
            for group in result.items
        ],
        total=result.total,
    )


def _load_action_history_by_group(
    session: Session, context: RequestContext
) -> dict[str, list[RemediationHistoryItem]]:
    actions = list(
        session.scalars(
            select(RemediationAction)
            .where(RemediationAction.organization_id == context.organization_id)
            .order_by(RemediationAction.occurred_at.desc(), RemediationAction.id.desc())
        ).all()
    )
    if not actions:
        return {}
    action_targets = list(
        session.scalars(
            select(RemediationActionTarget).where(
                RemediationActionTarget.organization_id == context.organization_id,
                RemediationActionTarget.action_id.in_({action.id for action in actions}),
            )
        ).all()
    )
    user_ids = {
        user_id
        for action in actions
        for user_id in (action.actor_user_id, action.revoked_by_user_id)
        if user_id is not None
    } | {
        target.revoked_by_user_id
        for target in action_targets
        if target.revoked_by_user_id is not None
    }
    users = {
        user.id: user.display_name
        for user in session.scalars(
            select(User).where(
                User.organization_id == context.organization_id,
                User.id.in_(user_ids),
            )
        ).all()
    }
    targets_by_action: dict[UUID, list[RemediationActionTarget]] = defaultdict(list)
    for target in action_targets:
        targets_by_action[target.action_id].append(target)

    def project_target_count(
        action: RemediationAction,
        targets: list[RemediationActionTarget],
    ) -> int:
        return len(
            {
                (
                    target.repository_id,
                    action.ecosystem,
                    _dependency_project_root(target.manifest_path),
                )
                for target in targets
            }
        )

    history: dict[str, list[RemediationHistoryItem]] = defaultdict(list)
    for action in actions:
        history[action.group_key].append(
            RemediationHistoryItem(
                id=str(action.id),
                event_type=action.action_type,
                watchback_state=action.watchback_state,
                reason_code=action.reason_code,
                note=action.note,
                actor_user_id=action.actor_user_id,
                actor_display_name=users.get(action.actor_user_id, "알 수 없는 사용자"),
                occurred_at=action.occurred_at,
                target_count=project_target_count(
                    action, targets_by_action[action.id]
                ),
                pull_requests=(action.result or {}).get("pull_requests", []),
            )
        )
        revoked_target_groups: dict[
            tuple[datetime, UUID, str | None], list[RemediationActionTarget]
        ] = defaultdict(list)
        for target in targets_by_action[action.id]:
            if target.revoked_at is not None and target.revoked_by_user_id is not None:
                revoked_target_groups[
                    (target.revoked_at, target.revoked_by_user_id, target.revocation_note)
                ].append(target)
        for (revoked_at, revoked_by, revocation_note), revoked_targets in (
            revoked_target_groups.items()
        ):
            history[action.group_key].append(
                RemediationHistoryItem(
                    id=f"{action.id}:revoked:{revoked_at.isoformat()}",
                    event_type="risk_acceptance_revoked",
                    watchback_state="accepted",
                    reason_code=None,
                    note=revocation_note,
                    actor_user_id=revoked_by,
                    actor_display_name=users.get(revoked_by, "알 수 없는 사용자"),
                    occurred_at=revoked_at,
                    target_count=project_target_count(action, revoked_targets),
                    pull_requests=[],
                )
            )
        if (
            not revoked_target_groups
            and action.revoked_at is not None
            and action.revoked_by_user_id is not None
        ):
            history[action.group_key].append(
                RemediationHistoryItem(
                    id=f"{action.id}:revoked",
                    event_type="risk_acceptance_revoked",
                    watchback_state="accepted",
                    reason_code=None,
                    note=action.revocation_note,
                    actor_user_id=action.revoked_by_user_id,
                    actor_display_name=users.get(
                        action.revoked_by_user_id, "알 수 없는 사용자"
                    ),
                    occurred_at=action.revoked_at,
                    target_count=project_target_count(
                        action, targets_by_action[action.id]
                    ),
                    pull_requests=[],
                )
            )
    for items in history.values():
        items.sort(key=lambda item: (item.occurred_at, item.id), reverse=True)
    return dict(history)


def _load_current_versions(
    session: Session, context: RequestContext
) -> dict[tuple[UUID, str | None, str, str], DependencyVersionSnapshot]:
    snapshots = session.scalars(
        select(DependencyVersionSnapshot)
        .where(DependencyVersionSnapshot.organization_id == context.organization_id)
        .order_by(
            DependencyVersionSnapshot.observed_at.desc(),
            DependencyVersionSnapshot.id.desc(),
        )
    ).all()
    latest: dict[
        tuple[UUID, str | None, str, str], DependencyVersionSnapshot
    ] = {}
    for snapshot in snapshots:
        key = (
            snapshot.repository_id,
            snapshot.manifest_path,
            snapshot.ecosystem,
            _canonical_package_name(snapshot.ecosystem, snapshot.package_name),
        )
        latest.setdefault(key, snapshot)
    return latest


def _load_candidate_details(
    session: Session, alert_ids: set[UUID]
) -> dict[UUID, CandidateDetail]:
    if not alert_ids:
        return {}
    candidates = session.scalars(
        select(RiskCandidate)
        .join(AlertCandidateMatch, AlertCandidateMatch.candidate_id == RiskCandidate.id)
        .where(AlertCandidateMatch.alert_id.in_(alert_ids))
        .distinct()
        .order_by(RiskCandidate.selected_at.asc(), RiskCandidate.id.asc())
    ).all()
    candidate_ids = {candidate.id for candidate in candidates}
    if not candidate_ids:
        return {}
    evidence_by_candidate: dict[UUID, list[EvidenceResponse]] = defaultdict(list)
    epss_observed_by_candidate_batch: dict[
        tuple[UUID, UUID], list[datetime]
    ] = defaultdict(list)
    evidence_seen: dict[UUID, set[tuple[object, ...]]] = defaultdict(set)
    evidence_rows = session.execute(
        select(CandidateEvidence, GoldBatch)
        .join(GoldBatch, GoldBatch.id == CandidateEvidence.batch_id)
        .where(CandidateEvidence.candidate_id.in_(candidate_ids))
        .order_by(
            CandidateEvidence.candidate_id.asc(),
            CandidateEvidence.observed_at.asc(),
            GoldBatch.source_generated_at.asc(),
            CandidateEvidence.id.asc(),
        )
    ).all()
    epss_signals = {
        "epss_score",
        "epss_percentile",
        "epss_score_d30",
        "epss_percentile_d30",
    }
    for item, batch in evidence_rows:
        if item.signal in epss_signals:
            epss_observed_by_candidate_batch[(item.candidate_id, batch.id)].append(
                item.observed_at
            )
        key = (
            item.signal,
            item.observed_at,
            item.previous_value,
            item.current_value,
            item.source,
        )
        if key in evidence_seen[item.candidate_id]:
            continue
        evidence_seen[item.candidate_id].add(key)
        evidence_by_candidate[item.candidate_id].append(
            EvidenceResponse(
                id=item.id,
                source_evidence_id=item.source_evidence_id,
                batch_id=item.batch_id,
                signal=normalize_evidence_signal(item.signal),
                value_type=item.value_type,
                previous_value=item.previous_value,
                current_value=item.current_value,
                observed_at=item.observed_at,
                source=item.source,
                evidence_summary=item.evidence_summary,
            )
        )

    deliveries_by_candidate: dict[UUID, list[CandidateDelivery]] = defaultdict(list)
    delivery_rows = session.execute(
        select(GoldBatchCandidate, GoldBatch)
        .join(GoldBatch, GoldBatch.id == GoldBatchCandidate.batch_id)
        .where(GoldBatchCandidate.candidate_id.in_(candidate_ids))
        .order_by(
            GoldBatchCandidate.candidate_id.asc(),
            GoldBatch.as_of.asc(),
            GoldBatch.id.asc(),
        )
    ).all()
    for delivery, batch in delivery_rows:
        deliveries_by_candidate[delivery.candidate_id].append(
            CandidateDelivery(
                batch_id=batch.id,
                source_batch_id=batch.source_batch_id,
                as_of=batch.as_of,
                source_generated_at=batch.source_generated_at,
                policy_version=batch.policy_version,
                schema_version=batch.schema_version,
                received_at=delivery.received_at,
                source_annotations=_source_annotations(
                    epss_observed_by_candidate_batch.get(
                        (delivery.candidate_id, batch.id), []
                    )
                ),
            )
        )
    return {
        candidate.id: CandidateDetail(
            id=candidate.id,
            source_candidate_id=candidate.source_candidate_id,
            subject_type=candidate.subject_type,
            subject_id=candidate.subject_id,
            ghsa_id=candidate.ghsa_id,
            cve_id=candidate.cve_id,
            priority=candidate.priority,
            change_type=normalize_change_type(candidate.change_type),
            reason_summary=candidate.reason_summary,
            selected_at=candidate.selected_at,
            deliveries=deliveries_by_candidate[candidate.id],
            evidence=evidence_by_candidate[candidate.id],
        )
        for candidate in candidates
    }


def _load_accepted_target_keys(
    session: Session, context: RequestContext
) -> set[tuple[UUID, UUID]]:
    return set(
        session.execute(
            select(
                RemediationActionTarget.alert_id,
                RemediationActionTarget.candidate_id,
            )
            .join(
                RemediationAction,
                RemediationAction.id == RemediationActionTarget.action_id,
            )
            .where(
                RemediationAction.organization_id == context.organization_id,
                RemediationAction.action_type == "risk_accepted",
                RemediationAction.watchback_state == "accepted",
                RemediationAction.revoked_at.is_(None),
                RemediationActionTarget.revoked_at.is_(None),
            )
        ).all()
    )


def _source_annotations(observed_values: list[datetime]) -> list[SourceAnnotation]:
    result: list[SourceAnnotation] = []
    seen: set[tuple[object, object]] = set()
    for observed_at in observed_values:
        for annotation in annotations_for_observed_at(observed_at):
            key = (annotation.snapshot_date, annotation.annotation_type)
            if key in seen:
                continue
            seen.add(key)
            result.append(
                SourceAnnotation(
                    snapshot_date=annotation.snapshot_date,
                    annotation_type=annotation.annotation_type,
                    label=annotation.label,
                    description=annotation.description,
                    source_url=annotation.source_url,
                )
            )
    return result


def _action_target_rows(
    rows: list[RemediationSourceRow],
    group_key: str,
    target_ids: list[str] | None = None,
) -> tuple[RemediationSourceRow, list[RemediationSourceRow]]:
    group_rows = [
        row
        for row in rows
        if _stable_id(
            row.organization_id,
            row.ecosystem,
            _canonical_package_name(row.ecosystem, row.package_name),
        )
        == group_key
    ]
    if not group_rows:
        raise ServiceError(
            404,
            "remediation_group_not_found",
            "패키지 조치 그룹을 찾을 수 없습니다.",
        )
    selected_target_ids = set(target_ids or [])
    known_target_ids = {_target_id(row) for row in group_rows}
    if selected_target_ids - known_target_ids:
        raise ServiceError(
            404,
            "remediation_target_not_found",
            "선택한 저장소·프로젝트 조치 대상을 찾을 수 없습니다.",
        )
    open_rows = {
        row.alert_id: row
        for row in group_rows
        if row.alert_state == "open"
        and (
            not selected_target_ids
            or _target_id(row) in selected_target_ids
        )
    }
    if not open_rows:
        raise ServiceError(
            409,
            "no_actionable_targets",
            "현재 조치할 Open Alert가 없습니다.",
        )
    return group_rows[0], sorted(
        open_rows.values(),
        key=lambda row: (
            row.repository_full_name,
            row.manifest_path or "",
            row.github_alert_number,
            str(row.alert_id),
        ),
    )


def _target_fingerprint(rows: list[RemediationSourceRow]) -> str:
    value = "\n".join(
        "\x1f".join(
            (
                str(row.case_id),
                str(row.candidate_id),
                str(row.alert_id),
                str(row.repository_id),
                row.repository_full_name,
                row.manifest_path or "",
                str(row.github_alert_number),
                row.alert_state,
            )
        )
        for row in rows
    )
    return sha256(value.encode("utf-8")).hexdigest()


def create_remediation_action(
    session: Session,
    context: RequestContext,
    group_key: str,
    request: RemediationActionCreate,
    *,
    now: datetime | None = None,
) -> RemediationActionCreated:
    representative, target_rows = _action_target_rows(
        _load_source_rows(session, context), group_key, request.target_ids
    )
    occurred_at = now or datetime.now(UTC)
    watchback_state = (
        WatchbackActionState.ACCEPTED
        if request.action_type == RemediationActionType.RISK_ACCEPTED
        else WatchbackActionState.REQUESTED
    )
    action = RemediationAction(
        id=uuid4(),
        organization_id=context.organization_id,
        actor_user_id=context.user_id,
        group_key=group_key,
        ecosystem=representative.ecosystem,
        package_name=_canonical_package_name(
            representative.ecosystem,
            representative.package_name,
        ),
        action_type=request.action_type.value,
        watchback_state=watchback_state.value,
        target_fingerprint=_target_fingerprint(target_rows),
        reason_code=(request.reason_code.value if request.reason_code else None),
        note=request.note,
        occurred_at=occurred_at,
    )
    targets = [
        RemediationActionTarget(
            id=uuid4(),
            organization_id=context.organization_id,
            action_id=action.id,
            review_case_id=row.case_id,
            candidate_id=row.candidate_id,
            alert_id=row.alert_id,
            repository_id=row.repository_id,
            repository_full_name=row.repository_full_name,
            manifest_path=row.manifest_path,
            github_alert_number=row.github_alert_number,
            github_alert_state_at_action=row.alert_state,
        )
        for row in target_rows
    ]
    try:
        session.add(action)
        session.add_all(targets)
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise ServiceError(
            409,
            "duplicate_remediation_action",
            "동일한 대상에 같은 패키지 조치가 이미 기록되었습니다.",
        ) from exc

    return RemediationActionCreated(
        id=action.id,
        organization_id=action.organization_id,
        actor_user_id=action.actor_user_id,
        group_key=action.group_key,
        ecosystem=action.ecosystem,
        package_name=action.package_name,
        action_type=action.action_type,
        watchback_state=action.watchback_state,
        reason_code=action.reason_code,
        note=action.note,
        occurred_at=action.occurred_at,
        targets=[
            RemediationActionTargetResponse(
                review_case_id=target.review_case_id,
                candidate_id=target.candidate_id,
                alert_id=target.alert_id,
                repository_id=target.repository_id,
                repository_full_name=target.repository_full_name,
                manifest_path=target.manifest_path,
                github_alert_number=target.github_alert_number,
                github_alert_state_at_action=target.github_alert_state_at_action,
            )
            for target in targets
        ],
    )


def create_remediation_pull_requests(
    session: Session,
    context: RequestContext,
    group_key: str,
    request: RemediationPullRequestCreate,
    *,
    github_token: str,
    now: datetime | None = None,
) -> RemediationPullRequestBatchCreated:
    from watchback_backend.remediation.github_pr import (
        GitHubRemediationError,
        create_package_update_pr,
    )

    representative, target_rows = _action_target_rows(
        _load_source_rows(session, context), group_key, request.target_ids
    )
    if representative.ecosystem.lower() not in {"npm", "pip"}:
        raise ServiceError(
            409,
            "unsupported_remediation_ecosystem",
            "현재 자동조치는 npm과 pip 직접 의존성만 지원합니다.",
        )
    if any(not _is_supported_remediation_dependency(row) for row in target_rows):
        raise ServiceError(
            409,
            "unsupported_remediation_dependency",
            "현재 자동조치는 runtime 직접 의존성만 지원합니다. "
            "pip pyproject.toml의 unknown 관계는 manifest 직접 선언을 검증한 뒤 허용합니다.",
        )

    fingerprint = _target_fingerprint(target_rows)
    existing = session.scalar(
        select(RemediationAction).where(
            RemediationAction.organization_id == context.organization_id,
            RemediationAction.group_key == group_key,
            RemediationAction.action_type == RemediationActionType.REMEDIATION_REQUESTED.value,
            RemediationAction.target_fingerprint == fingerprint,
            RemediationAction.revoked_at.is_(None),
            RemediationAction.result.is_not(None),
        )
    )
    if existing is not None:
        previous_pull_requests = list((existing.result or {}).get("pull_requests", []))
        previous_batch_closed = bool(previous_pull_requests) and all(
            pull_request.get("closed") for pull_request in previous_pull_requests
        )
        if (
            existing.watchback_state == WatchbackActionState.CANCELLED.value
            or previous_batch_closed
        ):
            existing.watchback_state = WatchbackActionState.CANCELLED.value
            existing.revoked_at = now or datetime.now(UTC)
            existing.revoked_by_user_id = context.user_id
            session.commit()
            existing = None
    if existing is not None:
        existing_targets = list(
            session.scalars(
                select(RemediationActionTarget).where(
                    RemediationActionTarget.organization_id == context.organization_id,
                    RemediationActionTarget.action_id == existing.id,
                )
            ).all()
        )
        return RemediationPullRequestBatchCreated(
            id=existing.id,
            organization_id=existing.organization_id,
            actor_user_id=existing.actor_user_id,
            group_key=existing.group_key,
            ecosystem=existing.ecosystem,
            package_name=existing.package_name,
            action_type=existing.action_type,
            watchback_state=existing.watchback_state,
            reason_code=existing.reason_code,
            note=existing.note,
            occurred_at=existing.occurred_at,
            targets=[
                RemediationActionTargetResponse(
                    review_case_id=target.review_case_id,
                    candidate_id=target.candidate_id,
                    alert_id=target.alert_id,
                    repository_id=target.repository_id,
                    repository_full_name=target.repository_full_name,
                    manifest_path=target.manifest_path,
                    github_alert_number=target.github_alert_number,
                    github_alert_state_at_action=target.github_alert_state_at_action,
                )
                for target in existing_targets
            ],
            pull_requests=(existing.result or {}).get("pull_requests", []),
        )

    grouped_targets: dict[str, list[RemediationSourceRow]] = defaultdict(list)
    for row in target_rows:
        grouped_targets[_target_id(row)].append(row)
    current_groups = list_remediation_groups(session, context)
    current_group = next((group for group in current_groups.items if group.id == group_key), None)
    if current_group is None:
        raise ServiceError(404, "remediation_group_not_found", "패키지 조치 그룹을 찾을 수 없습니다.")
    targets_by_id = {target.id: target for target in current_group.targets}

    results: list[dict] = []
    try:
        for target_id, rows in sorted(
            grouped_targets.items(), key=lambda item: item[1][0].repository_full_name
        ):
            target = targets_by_id[target_id]
            if target.current_version_status != "resolved" or len(target.current_versions) != 1:
                raise ServiceError(
                    409,
                    "current_version_unavailable",
                    f"{target.repository.full_name}의 현재 사용 버전을 하나로 확정할 수 없습니다.",
                )
            patched_versions = {
                row.first_patched_version for row in rows if row.first_patched_version
            }
            if not patched_versions:
                raise ServiceError(
                    409,
                    "patched_version_unavailable",
                    f"{target.repository.full_name}의 권장 수정 버전이 없습니다.",
                )
            target_version = str(max(Version(value) for value in patched_versions))
            result = create_package_update_pr(
                token=github_token,
                repository_full_name=target.repository.full_name,
                manifest_path=rows[0].manifest_path,
                package_name=current_group.package_name,
                current_version=target.current_versions[0],
                target_version=target_version,
                cve_ids=[row.cve_id for row in rows],
                alert_numbers=[row.github_alert_number for row in rows],
                ecosystem=current_group.ecosystem,
            )
            results.append(asdict(result))
    except ServiceError:
        raise
    except (GitHubRemediationError, InvalidVersion) as exc:
        raise ServiceError(502, "github_remediation_failed", str(exc)) from exc

    occurred_at = now or datetime.now(UTC)
    action = RemediationAction(
        id=uuid4(),
        organization_id=context.organization_id,
        actor_user_id=context.user_id,
        group_key=group_key,
        ecosystem=current_group.ecosystem,
        package_name=current_group.package_name,
        action_type=RemediationActionType.REMEDIATION_REQUESTED.value,
        watchback_state=WatchbackActionState.PR_OPEN.value,
        target_fingerprint=fingerprint,
        reason_code=None,
        note=request.note or "업데이트 PR 생성",
        result={"pull_requests": results},
        occurred_at=occurred_at,
    )
    action_targets = [
        RemediationActionTarget(
            id=uuid4(),
            organization_id=context.organization_id,
            action_id=action.id,
            review_case_id=row.case_id,
            candidate_id=row.candidate_id,
            alert_id=row.alert_id,
            repository_id=row.repository_id,
            repository_full_name=row.repository_full_name,
            manifest_path=row.manifest_path,
            github_alert_number=row.github_alert_number,
            github_alert_state_at_action=row.alert_state,
        )
        for row in target_rows
    ]
    try:
        session.add(action)
        session.add_all(action_targets)
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise ServiceError(
            409,
            "duplicate_remediation_action",
            "동일한 대상의 업데이트 PR이 이미 기록되었습니다.",
        ) from exc
    return RemediationPullRequestBatchCreated(
        id=action.id,
        organization_id=action.organization_id,
        actor_user_id=action.actor_user_id,
        group_key=action.group_key,
        ecosystem=action.ecosystem,
        package_name=action.package_name,
        action_type=action.action_type,
        watchback_state=action.watchback_state,
        reason_code=None,
        note=action.note,
        occurred_at=action.occurred_at,
        targets=[
            RemediationActionTargetResponse(
                review_case_id=target.review_case_id,
                candidate_id=target.candidate_id,
                alert_id=target.alert_id,
                repository_id=target.repository_id,
                repository_full_name=target.repository_full_name,
                manifest_path=target.manifest_path,
                github_alert_number=target.github_alert_number,
                github_alert_state_at_action=target.github_alert_state_at_action,
            )
            for target in action_targets
        ],
        pull_requests=[RemediationPullRequest.model_validate(item) for item in results],
    )


def close_remediation_pull_requests(
    session: Session,
    context: RequestContext,
    group_key: str,
    request: RemediationPullRequestMergeRequest,
    *,
    github_token: str,
) -> RemediationPullRequestCloseResponse:
    from watchback_backend.remediation.github_pr import (
        GitHubRemediationError,
        close_package_update_pr,
    )

    query = select(RemediationAction).where(
        RemediationAction.organization_id == context.organization_id,
        RemediationAction.group_key == group_key,
        RemediationAction.action_type == RemediationActionType.REMEDIATION_REQUESTED.value,
        RemediationAction.result.is_not(None),
    )
    if request.action_id is not None:
        query = query.where(RemediationAction.id == request.action_id)
    action = session.scalar(
        query.order_by(RemediationAction.occurred_at.desc(), RemediationAction.id.desc())
    )
    if action is None:
        raise ServiceError(404, "remediation_pull_request_not_found", "닫을 자동조치 PR 이력을 찾을 수 없습니다.")
    pull_requests = list((action.result or {}).get("pull_requests", []))
    if not pull_requests:
        raise ServiceError(409, "remediation_pull_request_not_found", "닫을 자동조치 PR이 없습니다.")

    updated: list[dict] = []
    try:
        for pull_request in pull_requests:
            if pull_request.get("closed"):
                updated.append(pull_request)
                continue
            result = close_package_update_pr(
                token=github_token,
                repository_full_name=pull_request["repository_full_name"],
                number=pull_request["number"],
            )
            updated.append({
                **pull_request,
                "closed": result.closed,
                "closed_at": result.closed_at,
            })
            action.result = {**(action.result or {}), "pull_requests": [*updated, *pull_requests[len(updated):]]}
            session.commit()
    except GitHubRemediationError as exc:
        raise ServiceError(409, "github_close_blocked", str(exc)) from exc

    action.watchback_state = WatchbackActionState.CANCELLED.value
    action.revoked_at = datetime.now(UTC)
    action.revoked_by_user_id = context.user_id
    action.result = {**(action.result or {}), "pull_requests": updated}
    session.commit()
    return RemediationPullRequestCloseResponse(
        action_id=action.id,
        group_key=action.group_key,
        watchback_state=action.watchback_state,
        pull_requests=[RemediationPullRequest.model_validate(item) for item in updated],
    )


def merge_remediation_pull_requests(
    session: Session,
    context: RequestContext,
    group_key: str,
    request: RemediationPullRequestMergeRequest,
    *,
    github_token: str,
) -> RemediationPullRequestMergeResponse:
    from watchback_backend.remediation.github_pr import (
        GitHubClient,
        GitHubRemediationError,
        merge_package_update_pr,
    )

    query = select(RemediationAction).where(
        RemediationAction.organization_id == context.organization_id,
        RemediationAction.group_key == group_key,
        RemediationAction.action_type == RemediationActionType.REMEDIATION_REQUESTED.value,
        RemediationAction.result.is_not(None),
    )
    if request.action_id is not None:
        query = query.where(RemediationAction.id == request.action_id)
    action = session.scalar(
        query.order_by(RemediationAction.occurred_at.desc(), RemediationAction.id.desc())
    )
    if action is None:
        raise ServiceError(
            404,
            "remediation_pull_request_not_found",
            "병합할 자동조치 PR 이력을 찾을 수 없습니다.",
        )
    pull_requests = list((action.result or {}).get("pull_requests", []))
    if not pull_requests:
        raise ServiceError(
            409,
            "remediation_pull_request_not_found",
            "병합할 자동조치 PR이 없습니다.",
        )

    updated: list[dict] = []
    try:
        for pull_request in pull_requests:
            if pull_request.get("merged"):
                updated.append(pull_request)
                continue
            merge_result = merge_package_update_pr(
                token=github_token,
                repository_full_name=pull_request["repository_full_name"],
                number=pull_request["number"],
                expected_head_ref=pull_request["head_ref"],
                expected_head_sha=pull_request["head_sha"],
                project_root=pull_request["project_root"],
                ecosystem=action.ecosystem,
            )
            merged_item = {
                **pull_request,
                "merged": merge_result.merged,
                "merge_sha": merge_result.merge_sha,
                "merged_at": merge_result.merged_at,
            }
            updated.append(merged_item)
            action.result = {**(action.result or {}), "pull_requests": [*updated, *pull_requests[len(updated):]]}
            session.commit()
    except GitHubRemediationError as exc:
        raise ServiceError(409, "github_merge_blocked", str(exc)) from exc

    action.watchback_state = WatchbackActionState.PR_MERGED.value
    action.result = {**(action.result or {}), "pull_requests": updated}
    session.commit()

    action_targets = list(
        session.scalars(
            select(RemediationActionTarget).where(
                RemediationActionTarget.organization_id == context.organization_id,
                RemediationActionTarget.action_id == action.id,
            )
        ).all()
    )
    alerts_by_id = {
        alert.id: alert
        for alert in session.scalars(
            select(DependabotAlert).where(
                DependabotAlert.organization_id == context.organization_id,
                DependabotAlert.id.in_({target.alert_id for target in action_targets}),
            )
        ).all()
    }
    github = GitHubClient(github_token)
    timeout = min(max(int(os.environ.get("REMEDIATION_VERIFY_TIMEOUT_SECONDS", "30")), 0), 60)
    deadline = time.monotonic() + timeout
    latest_payloads: dict[UUID, dict] = {}
    while True:
        for target in action_targets:
            if latest_payloads.get(target.alert_id, {}).get("state") == "fixed":
                continue
            payload = github.request(
                "GET",
                f"/repos/{target.repository_full_name}/dependabot/alerts/"
                f"{target.github_alert_number}",
            )
            package_name = ((payload.get("dependency") or {}).get("package") or {}).get("name")
            if _canonical_package_name(action.ecosystem, package_name or "") != action.package_name:
                raise ServiceError(
                    409,
                    "github_alert_package_mismatch",
                    "GitHub Alert의 패키지가 저장된 자동조치 대상과 다릅니다.",
                )
            latest_payloads[target.alert_id] = payload
        if all(payload.get("state") == "fixed" for payload in latest_payloads.values()):
            break
        if time.monotonic() >= deadline:
            break
        time.sleep(2)

    verified_at = datetime.now(UTC)
    verifications: list[RemediationAlertVerification] = []
    for target in action_targets:
        payload = latest_payloads[target.alert_id]
        github_updated_at = datetime.fromisoformat(payload["updated_at"].replace("Z", "+00:00"))
        fixed_at = (
            datetime.fromisoformat(payload["fixed_at"].replace("Z", "+00:00"))
            if payload.get("fixed_at")
            else None
        )
        alert = alerts_by_id[target.alert_id]
        if payload.get("state") == "fixed" and fixed_at is not None:
            alert.state = "fixed"
            alert.fixed_at = fixed_at
            alert.dismissed_at = None
            alert.dismissed_reason = None
            alert.dismissed_by = None
            alert.dismissed_comment = None
            alert.auto_dismissed_at = None
            alert.github_updated_at = github_updated_at
            alert.last_synced_at = verified_at
        verifications.append(
            RemediationAlertVerification(
                alert_id=target.alert_id,
                repository_full_name=target.repository_full_name,
                github_alert_number=target.github_alert_number,
                state=payload["state"],
                fixed_at=fixed_at,
                github_updated_at=github_updated_at,
            )
        )
    all_fixed = all(item.state.value == "fixed" for item in verifications)
    action.watchback_state = (
        WatchbackActionState.COMPLETED.value
        if all_fixed
        else WatchbackActionState.VERIFICATION_PENDING.value
    )
    action.result = {
        **(action.result or {}),
        "pull_requests": updated,
        "alert_verifications": [item.model_dump(mode="json") for item in verifications],
    }
    session.commit()
    return RemediationPullRequestMergeResponse(
        action_id=action.id,
        group_key=action.group_key,
        watchback_state=action.watchback_state,
        pull_requests=[RemediationPullRequest.model_validate(item) for item in updated],
        alert_verifications=verifications,
    )


def reopen_remediation_group(
    session: Session,
    context: RequestContext,
    group_key: str,
    *,
    target_ids: list[str] | None = None,
    note: str | None = None,
    now: datetime | None = None,
) -> RemediationReopened:
    rows = _load_source_rows(session, context)
    if not any(
        _stable_id(
            row.organization_id,
            row.ecosystem,
            _canonical_package_name(row.ecosystem, row.package_name),
        )
        == group_key
        for row in rows
    ):
        raise ServiceError(
            404,
            "remediation_group_not_found",
            "패키지 조치 그룹을 찾을 수 없습니다.",
        )
    selected_target_ids = set(target_ids or [])
    known_target_ids = {
        _target_id(row)
        for row in rows
        if _stable_id(
            row.organization_id,
            row.ecosystem,
            _canonical_package_name(row.ecosystem, row.package_name),
        )
        == group_key
    }
    if selected_target_ids - known_target_ids:
        raise ServiceError(
            404,
            "remediation_target_not_found",
            "선택한 저장소·프로젝트 조치 대상을 찾을 수 없습니다.",
        )
    actions = list(
        session.scalars(
            select(RemediationAction).where(
                RemediationAction.organization_id == context.organization_id,
                RemediationAction.group_key == group_key,
                RemediationAction.action_type == "risk_accepted",
                RemediationAction.watchback_state == "accepted",
                RemediationAction.revoked_at.is_(None),
            )
        ).all()
    )
    action_by_id = {action.id: action for action in actions}
    targets = list(
        session.scalars(
            select(RemediationActionTarget).where(
                RemediationActionTarget.organization_id == context.organization_id,
                RemediationActionTarget.action_id.in_(set(action_by_id)),
                RemediationActionTarget.revoked_at.is_(None),
            )
        ).all()
    )
    selected_targets = [
        target
        for target in targets
        if not selected_target_ids
        or _stable_id(
            target.repository_id,
            action_by_id[target.action_id].ecosystem,
            _dependency_project_root(target.manifest_path),
        ) in selected_target_ids
    ]
    if not selected_targets:
        raise ServiceError(
            409,
            "risk_acceptance_not_found",
            "현재 취소할 위험 수용 기록이 없습니다.",
        )
    reopened_at = now or datetime.now(UTC)
    normalized_note = note.strip() if note else None
    for target in selected_targets:
        target.revoked_at = reopened_at
        target.revoked_by_user_id = context.user_id
        target.revocation_note = normalized_note
    targets_by_action: dict[UUID, list[RemediationActionTarget]] = defaultdict(list)
    for target in targets:
        targets_by_action[target.action_id].append(target)
    revoked_action_ids: list[UUID] = []
    for action_id, action_targets in targets_by_action.items():
        if all(target.revoked_at is not None for target in action_targets):
            action = action_by_id[action_id]
            action.revoked_at = reopened_at
            action.revoked_by_user_id = context.user_id
            action.revocation_note = normalized_note
            revoked_action_ids.append(action.id)
    session.commit()
    return RemediationReopened(
        group_key=group_key,
        revoked_action_ids=revoked_action_ids,
        reopened_at=reopened_at,
    )
