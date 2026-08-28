from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Engine, create_engine, select, text
from sqlalchemy.orm import Session

from watchback_backend.db.models import (
    AlertCandidateMatch,
    DependabotAlert,
    GoldBatch,
    GoldBatchCandidate,
    Organization,
    Repository,
    ReviewActivity,
    ReviewCase,
    RiskCandidate,
    SecurityAdvisory,
)


LOCK_KEY = 920093
SAMPLE_LIMIT = 5


class CaseGenerationError(Exception):
    def __init__(self, code: str, message: str, **context: object) -> None:
        super().__init__(message)
        self.code = code
        self.context = context


@dataclass(frozen=True)
class CaseBasis:
    alert: DependabotAlert
    advisory: SecurityAdvisory
    repository: Repository
    candidate: RiskCandidate
    delivery: GoldBatchCandidate
    batch: GoldBatch


def _basis_trace(basis: CaseBasis, case_id: UUID | None = None) -> dict[str, object]:
    return {
        "case_id": str(case_id) if case_id else None,
        "repository": basis.repository.full_name,
        "alert_number": basis.alert.github_alert_number,
        "package": basis.alert.package_name,
        "manifest": basis.alert.manifest_path,
        "candidate_id": basis.candidate.source_candidate_id,
        "candidate_priority": basis.candidate.priority,
        "case_priority": basis.advisory.severity,
        "change_type": basis.candidate.change_type,
        "batch_id": basis.batch.source_batch_id,
        "policy_version": basis.batch.policy_version,
        "as_of": basis.batch.as_of.isoformat(),
    }


def _load_bases(
    session: Session, organization_id: UUID
) -> tuple[list[CaseBasis], dict[str, int], list[dict[str, object]]]:
    rows = list(
        session.execute(
            select(
                AlertCandidateMatch,
                DependabotAlert,
                SecurityAdvisory,
                Repository,
                RiskCandidate,
            )
            .join(DependabotAlert, DependabotAlert.id == AlertCandidateMatch.alert_id)
            .join(SecurityAdvisory, SecurityAdvisory.id == DependabotAlert.advisory_id)
            .join(Repository, Repository.id == DependabotAlert.repository_id)
            .join(RiskCandidate, RiskCandidate.id == AlertCandidateMatch.candidate_id)
            .where(AlertCandidateMatch.organization_id == organization_id)
        )
    )
    by_case: dict[tuple[UUID, str], list[Any]] = defaultdict(list)
    non_open_alerts: set[UUID] = set()
    for row in rows:
        if row.DependabotAlert.state == "open":
            by_case[(row.Repository.id, row.SecurityAdvisory.cve_id)].append(row)
        else:
            non_open_alerts.add(row.DependabotAlert.id)

    representatives = [
        max(
            alert_rows,
            key=lambda row: (row.RiskCandidate.selected_at, str(row.RiskCandidate.id)),
        )
        for alert_rows in by_case.values()
    ]
    candidate_ids = [row.RiskCandidate.id for row in representatives]
    deliveries: dict[UUID, list[Any]] = defaultdict(list)
    if candidate_ids:
        for row in session.execute(
            select(GoldBatchCandidate, GoldBatch)
            .join(GoldBatch, GoldBatch.id == GoldBatchCandidate.batch_id)
            .where(GoldBatchCandidate.candidate_id.in_(candidate_ids))
        ):
            deliveries[row.GoldBatchCandidate.candidate_id].append(row)

    bases: list[CaseBasis] = []
    excluded: list[dict[str, object]] = []
    for row in representatives:
        candidate_deliveries = deliveries.get(row.RiskCandidate.id, [])
        if not candidate_deliveries:
            excluded.append(
                {
                    "reason": "candidate_delivery_not_found",
                    "repository": row.Repository.full_name,
                    "alert_number": row.DependabotAlert.github_alert_number,
                    "candidate_id": row.RiskCandidate.source_candidate_id,
                }
            )
            continue
        delivery_row = max(
            candidate_deliveries,
            key=lambda item: (
                item.GoldBatch.source_generated_at,
                item.GoldBatch.as_of,
                str(item.GoldBatch.id),
            ),
        )
        bases.append(
            CaseBasis(
                alert=row.DependabotAlert,
                advisory=row.SecurityAdvisory,
                repository=row.Repository,
                candidate=row.RiskCandidate,
                delivery=delivery_row.GoldBatchCandidate,
                batch=delivery_row.GoldBatch,
            )
        )

    return (
        sorted(
            bases,
            key=lambda basis: (
                basis.repository.full_name,
                basis.alert.github_alert_number,
            ),
        ),
        {
            "match_count": len(rows),
            "open_alert_count": len(
                {
                    row.DependabotAlert.id
                    for rows_for_case in by_case.values()
                    for row in rows_for_case
                }
            ),
            "non_open_alert_count": len(non_open_alerts),
        },
        excluded,
    )


def run_case_generation(
    database_url: str,
    organization_id: UUID,
    *,
    dry_run: bool = False,
    occurred_at: datetime | None = None,
    engine: Engine | None = None,
) -> dict[str, object]:
    owns_engine = engine is None
    database_engine = engine or create_engine(database_url, pool_pre_ping=True)
    timestamp = occurred_at or datetime.now(UTC)
    try:
        with Session(database_engine) as session, session.begin():
            locked = session.scalar(
                text("SELECT pg_try_advisory_xact_lock(:lock_key)"),
                {"lock_key": LOCK_KEY},
            )
            if not locked:
                raise CaseGenerationError(
                    "case_generation_already_running",
                    "다른 재검토 Case 생성 작업이 실행 중입니다.",
                )
            organization_exists = session.scalar(
                select(Organization.id).where(Organization.id == organization_id)
            )
            if organization_exists is None:
                raise CaseGenerationError(
                    "organization_not_found",
                    "Case 생성 대상 조직이 존재하지 않습니다.",
                    organization_id=str(organization_id),
                )

            bases, inputs, excluded = _load_bases(session, organization_id)
            existing_cases = {
                (repository_id, cve_id): review_case
                for review_case, repository_id, cve_id in session.execute(
                    select(
                        ReviewCase,
                        DependabotAlert.repository_id,
                        SecurityAdvisory.cve_id,
                    )
                    .join(DependabotAlert, DependabotAlert.id == ReviewCase.alert_id)
                    .join(
                        SecurityAdvisory,
                        SecurityAdvisory.id == DependabotAlert.advisory_id,
                    )
                    .where(ReviewCase.organization_id == organization_id)
                    .with_for_update(of=ReviewCase)
                )
            }
            inputs["existing_case_count"] = len(existing_cases)
            counts: Counter[str] = Counter()
            samples: dict[str, list[dict[str, object]]] = {
                "created": [],
                "updated": [],
                "reopened": [],
                "unchanged": [],
                "excluded": excluded[:SAMPLE_LIMIT],
            }

            for basis in bases:
                case_key = (basis.repository.id, basis.advisory.cve_id)
                review_case = existing_cases.get(case_key)
                action: str
                if review_case is None:
                    action = "created"
                    if not dry_run:
                        review_case = ReviewCase(
                            id=uuid4(),
                            organization_id=organization_id,
                            alert_id=basis.alert.id,
                            representative_candidate_id=basis.candidate.id,
                            representative_batch_id=basis.batch.id,
                            status="open",
                            priority=basis.advisory.severity,
                            review_reason=basis.candidate.reason_summary,
                            opened_at=timestamp,
                            reopened_count=0,
                            updated_at=timestamp,
                        )
                        session.add(review_case)
                        session.flush()
                        session.add(
                            ReviewActivity(
                                id=uuid4(),
                                organization_id=organization_id,
                                review_case_id=review_case.id,
                                actor_user_id=None,
                                candidate_id=basis.candidate.id,
                                activity_type="case_opened",
                                note=None,
                                occurred_at=timestamp,
                            )
                        )
                        existing_cases[case_key] = review_case
                elif review_case.status == "resolved":
                    if review_case.representative_candidate_id != basis.candidate.id:
                        action = "reopened"
                        if not dry_run:
                            review_case.representative_candidate_id = basis.candidate.id
                            review_case.representative_batch_id = basis.batch.id
                            review_case.status = "open"
                            review_case.priority = basis.advisory.severity
                            review_case.review_reason = basis.candidate.reason_summary
                            review_case.resolved_at = None
                            review_case.last_reopened_at = timestamp
                            review_case.reopened_count += 1
                            review_case.updated_at = timestamp
                            session.add(
                                ReviewActivity(
                                    id=uuid4(),
                                    organization_id=organization_id,
                                    review_case_id=review_case.id,
                                    actor_user_id=None,
                                    candidate_id=basis.candidate.id,
                                    activity_type="case_reopened",
                                    note=None,
                                    occurred_at=timestamp,
                                )
                            )
                    else:
                        action = "unchanged"
                else:
                    changed = (
                        review_case.representative_candidate_id != basis.candidate.id
                        or review_case.representative_batch_id != basis.batch.id
                        or review_case.priority != basis.advisory.severity
                        or review_case.review_reason != basis.candidate.reason_summary
                    )
                    action = "updated" if changed else "unchanged"
                    if changed and not dry_run:
                        review_case.representative_candidate_id = basis.candidate.id
                        review_case.representative_batch_id = basis.batch.id
                        review_case.priority = basis.advisory.severity
                        review_case.review_reason = basis.candidate.reason_summary
                        review_case.updated_at = timestamp

                counts[action] += 1
                if len(samples[action]) < SAMPLE_LIMIT:
                    case_id = review_case.id if review_case is not None else None
                    samples[action].append(_basis_trace(basis, case_id))

            counts["excluded"] = len(excluded)
            return {
                "organization_id": str(organization_id),
                "dry_run": dry_run,
                "db_applied": not dry_run,
                "inputs": inputs,
                "cases": {
                    key: counts[key]
                    for key in (
                        "created",
                        "updated",
                        "reopened",
                        "unchanged",
                        "excluded",
                    )
                },
                "excluded": {
                    "reasons": dict(Counter(item["reason"] for item in excluded)),
                    "non_open_alert_count": inputs["non_open_alert_count"],
                },
                "samples": samples,
            }
    finally:
        if owns_engine:
            database_engine.dispose()
