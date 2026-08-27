from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse
from uuid import UUID, uuid4

from sqlalchemy import Select, case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from watchback_backend.api.schemas import (
    ActorSummary,
    AlertDetail,
    AlertSummary,
    CandidateDelivery,
    CandidateDetail,
    CandidateSummary,
    CaseSort,
    CaseStatus,
    CaseStatusFilter,
    CreatedReviewActivityResponse,
    EvidenceResponse,
    ExternalLinkResponse,
    Priority,
    RepositorySummary,
    ReviewActivityCreate,
    ReviewActivityCreated,
    ReviewActivityResponse,
    ReviewCaseDetail,
    ReviewCaseListResponse,
    ReviewCaseSummary,
    SortOrder,
    UserActivityType,
    AdvisorySummary,
)
from watchback_backend.db.models import (
    AlertCandidateMatch,
    CandidateEvidence,
    DependabotAlert,
    ExternalLink,
    GoldBatch,
    GoldBatchCandidate,
    Repository,
    ReviewActivity,
    ReviewCase,
    RiskCandidate,
    SecurityAdvisory,
    User,
)


class ServiceError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


@dataclass(frozen=True)
class RequestContext:
    organization_id: UUID
    user_id: UUID
    display_name: str


def require_context(
    session: Session, organization_id: UUID, user_id: UUID
) -> RequestContext:
    user = session.scalar(
        select(User).where(
            User.id == user_id,
            User.organization_id == organization_id,
        )
    )
    if user is None:
        raise ServiceError(
            403,
            "organization_scope_violation",
            "요청한 조직 범위에 접근할 수 없습니다.",
        )
    return RequestContext(organization_id, user.id, user.display_name)


def _summary_query() -> Select[tuple[Any, ...]]:
    latest_kev_value = (
        select(CandidateEvidence.current_value)
        .join(
            AlertCandidateMatch,
            AlertCandidateMatch.candidate_id == CandidateEvidence.candidate_id,
        )
        .where(
            AlertCandidateMatch.alert_id == ReviewCase.alert_id,
            CandidateEvidence.signal == "kev",
        )
        .order_by(CandidateEvidence.observed_at.desc(), CandidateEvidence.id.desc())
        .limit(1)
        .correlate(ReviewCase)
        .scalar_subquery()
    )
    return (
        select(
            ReviewCase,
            Repository,
            DependabotAlert,
            SecurityAdvisory,
            RiskCandidate.id.label("candidate_id"),
            RiskCandidate.source_candidate_id,
            RiskCandidate.subject_type,
            RiskCandidate.subject_id,
            RiskCandidate.ghsa_id.label("candidate_ghsa_id"),
            RiskCandidate.cve_id,
            RiskCandidate.priority.label("candidate_priority"),
            RiskCandidate.change_type,
            RiskCandidate.reason_summary,
            RiskCandidate.selected_at,
            latest_kev_value.label("latest_kev_value"),
        )
        .join(DependabotAlert, DependabotAlert.id == ReviewCase.alert_id)
        .join(Repository, Repository.id == DependabotAlert.repository_id)
        .join(SecurityAdvisory, SecurityAdvisory.id == DependabotAlert.advisory_id)
        .join(
            RiskCandidate,
            RiskCandidate.id == ReviewCase.representative_candidate_id,
        )
    )


def _candidate_summary_from_mapping(row: Any) -> CandidateSummary:
    return CandidateSummary(
        id=row.candidate_id,
        source_candidate_id=row.source_candidate_id,
        subject_type=row.subject_type,
        subject_id=row.subject_id,
        ghsa_id=row.candidate_ghsa_id,
        cve_id=row.cve_id,
        priority=row.candidate_priority,
        change_type=row.change_type,
        reason_summary=row.reason_summary,
        selected_at=row.selected_at,
    )


def _summary_from_row(row: Any) -> ReviewCaseSummary:
    review_case = row.ReviewCase
    repository = row.Repository
    alert = row.DependabotAlert
    advisory = row.SecurityAdvisory
    return ReviewCaseSummary(
        id=review_case.id,
        is_kev=str(row.latest_kev_value).strip().lower() == "true",
        status=review_case.status,
        priority=review_case.priority,
        review_reason=review_case.review_reason,
        opened_at=review_case.opened_at,
        resolved_at=review_case.resolved_at,
        last_reopened_at=review_case.last_reopened_at,
        reopened_count=review_case.reopened_count,
        updated_at=review_case.updated_at,
        repository=RepositorySummary(
            id=repository.id,
            full_name=repository.full_name,
            display_name=repository.display_name,
            importance=repository.importance,
        ),
        alert=AlertSummary(
            id=alert.id,
            github_alert_number=alert.github_alert_number,
            state=alert.state,
            package_name=alert.package_name,
            ecosystem=alert.ecosystem,
            first_patched_version=alert.first_patched_version,
            html_url=alert.html_url,
        ),
        advisory=AdvisorySummary(
            ghsa_id=advisory.ghsa_id,
            cve_id=advisory.cve_id,
            summary=advisory.summary,
            severity=advisory.severity,
            cvss_score=advisory.cvss_score,
        ),
        latest_candidate=_candidate_summary_from_mapping(row),
    )


def list_review_cases(
    session: Session,
    context: RequestContext,
    *,
    case_status: CaseStatusFilter,
    priority: Priority | None,
    change_type: str | None,
    sort: CaseSort,
    order: SortOrder,
    page: int,
    page_size: int,
) -> ReviewCaseListResponse:
    query = _summary_query().where(
        ReviewCase.organization_id == context.organization_id
    )
    if case_status is not CaseStatusFilter.ALL:
        query = query.where(ReviewCase.status == case_status.value)
    if priority is not None:
        query = query.where(ReviewCase.priority == priority.value)
    if change_type is not None:
        query = query.where(RiskCandidate.change_type == change_type)

    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    direction = "asc" if order is SortOrder.ASC else "desc"
    if sort is CaseSort.PRIORITY:
        priority_rank = case(
            (ReviewCase.priority == "low", 1),
            (ReviewCase.priority == "medium", 2),
            (ReviewCase.priority == "high", 3),
            (ReviewCase.priority == "critical", 4),
            else_=0,
        )
        query = query.order_by(
            getattr(priority_rank, direction)(),
            ReviewCase.updated_at.desc(),
            ReviewCase.id.asc(),
        )
    else:
        sort_column = (
            ReviewCase.opened_at
            if sort is CaseSort.OPENED_AT
            else ReviewCase.updated_at
        )
        query = query.order_by(
            getattr(sort_column, direction)(),
            ReviewCase.id.asc(),
        )

    rows = session.execute(query.offset((page - 1) * page_size).limit(page_size)).all()
    return ReviewCaseListResponse(
        items=[_summary_from_row(row) for row in rows],
        page=page,
        page_size=page_size,
        total=total,
    )


def _case_row(
    session: Session, context: RequestContext, case_id: UUID, *, lock: bool = False
) -> Any:
    organization_id = session.scalar(
        select(ReviewCase.organization_id).where(ReviewCase.id == case_id)
    )
    if organization_id is None:
        raise ServiceError(
            404, "review_case_not_found", "재검토 Case를 찾을 수 없습니다."
        )
    if organization_id != context.organization_id:
        raise ServiceError(
            403,
            "organization_scope_violation",
            "요청한 조직 범위에 접근할 수 없습니다.",
        )

    query = _summary_query().where(ReviewCase.id == case_id)
    if lock:
        query = query.with_for_update(of=ReviewCase)
    row = session.execute(query).one_or_none()
    if row is None:
        raise ServiceError(
            404, "review_case_not_found", "재검토 Case를 찾을 수 없습니다."
        )
    return row


def _external_link_response(link: ExternalLink) -> ExternalLinkResponse:
    return ExternalLinkResponse(
        id=link.id,
        link_type=link.link_type,
        url=link.url,
        github_owner=link.github_owner,
        github_repository=link.github_repository,
        github_number=link.github_number,
        external_state=link.external_state,
        github_updated_at=link.github_updated_at,
        last_synced_at=link.last_synced_at,
    )


def get_review_case(
    session: Session, context: RequestContext, case_id: UUID
) -> ReviewCaseDetail:
    row = _case_row(session, context, case_id)
    summary = _summary_from_row(row)
    review_case = row.ReviewCase
    alert = row.DependabotAlert

    candidates = session.scalars(
        select(RiskCandidate)
        .join(AlertCandidateMatch, AlertCandidateMatch.candidate_id == RiskCandidate.id)
        .where(AlertCandidateMatch.alert_id == review_case.alert_id)
        .order_by(RiskCandidate.selected_at.asc(), RiskCandidate.id.asc())
    ).all()

    candidate_details: list[CandidateDetail] = []
    for candidate in candidates:
        delivery_rows = session.execute(
            select(GoldBatchCandidate, GoldBatch)
            .join(GoldBatch, GoldBatch.id == GoldBatchCandidate.batch_id)
            .where(GoldBatchCandidate.candidate_id == candidate.id)
            .order_by(GoldBatch.as_of.asc(), GoldBatch.id.asc())
        ).all()
        evidence_rows = session.execute(
            select(CandidateEvidence, GoldBatch)
            .join(GoldBatch, GoldBatch.id == CandidateEvidence.batch_id)
            .where(CandidateEvidence.candidate_id == candidate.id)
            .order_by(
                CandidateEvidence.observed_at.asc(),
                GoldBatch.source_generated_at.asc(),
                CandidateEvidence.id.asc(),
            )
        ).all()
        unique_evidence: list[CandidateEvidence] = []
        evidence_keys: set[tuple[object, ...]] = set()
        for evidence, _batch in evidence_rows:
            key = (
                evidence.signal,
                evidence.observed_at,
                evidence.previous_value,
                evidence.current_value,
                evidence.source,
            )
            if key in evidence_keys:
                continue
            evidence_keys.add(key)
            unique_evidence.append(evidence)
        candidate_details.append(
            CandidateDetail(
                id=candidate.id,
                source_candidate_id=candidate.source_candidate_id,
                subject_type=candidate.subject_type,
                subject_id=candidate.subject_id,
                ghsa_id=candidate.ghsa_id,
                cve_id=candidate.cve_id,
                priority=candidate.priority,
                change_type=candidate.change_type,
                reason_summary=candidate.reason_summary,
                selected_at=candidate.selected_at,
                deliveries=[
                    CandidateDelivery(
                        batch_id=batch.id,
                        source_batch_id=batch.source_batch_id,
                        as_of=batch.as_of,
                        source_generated_at=batch.source_generated_at,
                        policy_version=batch.policy_version,
                        schema_version=batch.schema_version,
                        received_at=delivery.received_at,
                    )
                    for delivery, batch in delivery_rows
                ],
                evidence=[
                    EvidenceResponse(
                        id=evidence.id,
                        source_evidence_id=evidence.source_evidence_id,
                        batch_id=evidence.batch_id,
                        signal=evidence.signal,
                        value_type=evidence.value_type,
                        previous_value=evidence.previous_value,
                        current_value=evidence.current_value,
                        observed_at=evidence.observed_at,
                        source=evidence.source,
                        evidence_summary=evidence.evidence_summary,
                    )
                    for evidence in unique_evidence
                ],
            )
        )

    activity_rows = session.execute(
        select(ReviewActivity, User)
        .outerjoin(User, User.id == ReviewActivity.actor_user_id)
        .where(ReviewActivity.review_case_id == case_id)
        .order_by(ReviewActivity.occurred_at.asc(), ReviewActivity.id.asc())
    ).all()
    activity_ids = [activity.id for activity, _ in activity_rows]
    links_by_activity: dict[UUID, list[ExternalLink]] = defaultdict(list)
    if activity_ids:
        links = session.scalars(
            select(ExternalLink)
            .where(ExternalLink.created_by_activity_id.in_(activity_ids))
            .order_by(ExternalLink.created_at.asc(), ExternalLink.id.asc())
        ).all()
        for link in links:
            links_by_activity[link.created_by_activity_id].append(link)

    activities = [
        ReviewActivityResponse(
            id=activity.id,
            candidate_id=activity.candidate_id,
            activity_type=activity.activity_type,
            note=activity.note,
            actor=(
                ActorSummary(id=actor.id, display_name=actor.display_name)
                if actor is not None
                else None
            ),
            occurred_at=activity.occurred_at,
            created_at=activity.created_at,
            external_links=[
                _external_link_response(link) for link in links_by_activity[activity.id]
            ],
        )
        for activity, actor in activity_rows
    ]

    return ReviewCaseDetail(
        **summary.model_dump(exclude={"alert"}),
        alert=AlertDetail(
            **summary.alert.model_dump(),
            manifest_path=alert.manifest_path,
            dependency_scope=alert.dependency_scope,
            dependency_relationship=alert.dependency_relationship,
            vulnerable_version_range=alert.vulnerable_version_range,
            github_created_at=alert.github_created_at,
            github_updated_at=alert.github_updated_at,
            dismissed_at=alert.dismissed_at,
            dismissed_reason=alert.dismissed_reason,
            dismissed_by=alert.dismissed_by,
            dismissed_comment=alert.dismissed_comment,
            fixed_at=alert.fixed_at,
            auto_dismissed_at=alert.auto_dismissed_at,
        ),
        candidates=candidate_details,
        activities=activities,
    )


def _constraint_name(exc: IntegrityError) -> str | None:
    diagnostic = getattr(getattr(exc, "orig", None), "diag", None)
    return getattr(diagnostic, "constraint_name", None)


def create_review_activity(
    session: Session,
    context: RequestContext,
    case_id: UUID,
    payload: ReviewActivityCreate,
) -> ReviewActivityCreated:
    activity: ReviewActivity | None = None
    external_link: ExternalLink | None = None
    case_status: str | None = None
    try:
        row = _case_row(session, context, case_id, lock=True)
        review_case = row.ReviewCase
        candidate_id = payload.candidate_id
        if candidate_id is not None:
            linked = session.scalar(
                select(AlertCandidateMatch.candidate_id).where(
                    AlertCandidateMatch.alert_id == review_case.alert_id,
                    AlertCandidateMatch.candidate_id == candidate_id,
                )
            )
            if linked is None:
                raise ServiceError(
                    404,
                    "candidate_not_found",
                    "이 Case에 연결된 위험 후보를 찾을 수 없습니다.",
                )
        candidate_match = (
            ReviewActivity.candidate_id.is_(None)
            if candidate_id is None
            else ReviewActivity.candidate_id == candidate_id
        )
        duplicate = session.scalar(
            select(ReviewActivity.id).where(
                ReviewActivity.review_case_id == case_id,
                candidate_match,
                ReviewActivity.activity_type == payload.activity_type.value,
            )
        )
        if duplicate is not None:
            raise ServiceError(
                409,
                "duplicate_activity",
                "동일 Candidate에 같은 활동이 이미 기록되었습니다.",
            )
        if payload.external_link is not None:
            url = str(payload.external_link.url)
            duplicate_url = session.scalar(
                select(ExternalLink.id).where(
                    ExternalLink.organization_id == context.organization_id,
                    ExternalLink.url == url,
                )
            )
            if duplicate_url is not None:
                raise ServiceError(
                    409,
                    "duplicate_external_link",
                    "조직에 같은 외부 링크가 이미 등록되어 있습니다.",
                )

        now = datetime.now(UTC)
        activity = ReviewActivity(
            id=uuid4(),
            organization_id=context.organization_id,
            review_case_id=case_id,
            actor_user_id=context.user_id,
            candidate_id=candidate_id,
            activity_type=payload.activity_type.value,
            note=payload.note,
            occurred_at=now,
        )
        session.add(activity)
        session.flush()

        if (
            payload.activity_type is UserActivityType.RISK_ACCEPTED
            and review_case.status == CaseStatus.OPEN.value
        ):
            review_case.status = CaseStatus.RESOLVED.value
            review_case.resolved_at = now

        if payload.external_link is not None:
            parsed = urlparse(str(payload.external_link.url))
            path_parts = [part for part in parsed.path.split("/") if part]
            external_link = ExternalLink(
                id=uuid4(),
                organization_id=context.organization_id,
                review_case_id=case_id,
                created_by_activity_id=activity.id,
                link_type=payload.external_link.link_type.value,
                url=str(payload.external_link.url),
                github_owner=path_parts[0],
                github_repository=path_parts[1],
                github_number=int(path_parts[3]),
                external_state=None,
                github_updated_at=None,
                last_synced_at=None,
            )
            session.add(external_link)
            session.flush()
        case_status = review_case.status
        session.commit()
    except ServiceError:
        session.rollback()
        raise
    except IntegrityError as exc:
        session.rollback()
        constraint_name = _constraint_name(exc)
        if (
            constraint_name
            == "uq_review_activities_review_case_id_candidate_id_activity_type"
        ):
            raise ServiceError(
                409,
                "duplicate_activity",
                "동일 Candidate에 같은 활동이 이미 기록되었습니다.",
            ) from exc
        if constraint_name == "uq_external_links_organization_id_url":
            raise ServiceError(
                409,
                "duplicate_external_link",
                "조직에 같은 외부 링크가 이미 등록되어 있습니다.",
            ) from exc
        raise

    assert activity is not None and case_status is not None
    return ReviewActivityCreated(
        case_status=case_status,
        activity=CreatedReviewActivityResponse(
            id=activity.id,
            candidate_id=activity.candidate_id,
            activity_type=activity.activity_type,
            note=activity.note,
            actor=ActorSummary(id=context.user_id, display_name=context.display_name),
            occurred_at=activity.occurred_at,
            created_at=activity.created_at,
            external_links=(
                [_external_link_response(external_link)]
                if external_link is not None
                else []
            ),
        ),
    )
