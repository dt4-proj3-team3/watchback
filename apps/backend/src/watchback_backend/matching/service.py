from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Engine, create_engine, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from watchback_backend.db.models import (
    AlertCandidateMatch,
    DependabotAlert,
    GoldBatch,
    GoldBatchCandidate,
    Organization,
    Repository,
    RiskCandidate,
    SecurityAdvisory,
)


LOCK_KEY = 920092
SAMPLE_LIMIT = 5
CVE_PATTERN = re.compile(r"^CVE-\d{4}-\d{4,}$")
GHSA_PATTERN = re.compile(r"^GHSA-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$")


class MatchingError(Exception):
    def __init__(self, code: str, message: str, **context: object) -> None:
        super().__init__(message)
        self.code = code
        self.context = context


def normalize_cve(value: str | None) -> str | None:
    normalized = value.strip().upper() if value else None
    return normalized if normalized and CVE_PATTERN.fullmatch(normalized) else None


def normalize_ghsa(value: str | None) -> str | None:
    normalized = value.strip().upper() if value else None
    return normalized if normalized and GHSA_PATTERN.fullmatch(normalized) else None


def _candidate_trace(
    candidate: Any,
    deliveries: dict[UUID, list[dict[str, str]]],
) -> dict[str, object]:
    return {
        "candidate_id": candidate.source_candidate_id,
        "subject_type": candidate.subject_type,
        "subject_id": candidate.subject_id,
        "cve_id": candidate.cve_id,
        "ghsa_id": candidate.ghsa_id,
        "batches": deliveries.get(candidate.id, []),
    }


def _match_trace(
    candidate: Any,
    alert: Any,
    advisory: Any,
    repository: Any,
    deliveries: dict[UUID, list[dict[str, str]]],
) -> dict[str, object]:
    return {
        **_candidate_trace(candidate, deliveries),
        "repository": repository.full_name,
        "alert_number": alert.github_alert_number,
        "alert_state": alert.state,
        "package": alert.package_name,
        "manifest": alert.manifest_path,
        "advisory_cve_id": advisory.cve_id,
        "advisory_ghsa_id": advisory.ghsa_id,
    }


def _load_deliveries(connection: Any) -> dict[UUID, list[dict[str, str]]]:
    rows = connection.execute(
        select(
            GoldBatchCandidate.candidate_id,
            GoldBatch.source_batch_id,
            GoldBatch.as_of,
        )
        .join(GoldBatch, GoldBatch.id == GoldBatchCandidate.batch_id)
        .order_by(GoldBatch.as_of, GoldBatch.source_batch_id)
    )
    deliveries: dict[UUID, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        deliveries[row.candidate_id].append(
            {
                "batch_id": row.source_batch_id,
                "as_of": row.as_of.isoformat(),
            }
        )
    return deliveries


def _calculate(
    connection: Any,
    organization_id: UUID,
) -> tuple[dict[str, object], list[tuple[UUID, UUID]]]:
    candidates = list(
        connection.scalars(
            select(RiskCandidate).order_by(
                RiskCandidate.selected_at, RiskCandidate.source_candidate_id
            )
        )
    )
    alert_rows = list(
        connection.execute(
            select(DependabotAlert, SecurityAdvisory, Repository)
            .join(SecurityAdvisory, SecurityAdvisory.id == DependabotAlert.advisory_id)
            .join(Repository, Repository.id == DependabotAlert.repository_id)
            .where(DependabotAlert.organization_id == organization_id)
            .order_by(Repository.full_name, DependabotAlert.github_alert_number)
        )
    )
    deliveries = _load_deliveries(connection)

    open_by_cve: dict[tuple[str, str], list[Any]] = defaultdict(list)
    all_by_cve: dict[tuple[str, str], list[Any]] = defaultdict(list)
    any_ghsa_by_cve: dict[str, set[str]] = defaultdict(set)
    open_by_ghsa: dict[str, list[Any]] = defaultdict(list)
    all_by_ghsa: dict[str, list[Any]] = defaultdict(list)
    alert_states: Counter[str] = Counter()
    invalid_alerts = 0

    for row in alert_rows:
        alert, advisory, _repository = row
        alert_states[alert.state] += 1
        ghsa = normalize_ghsa(advisory.ghsa_id)
        cve = normalize_cve(advisory.cve_id)
        if ghsa is None or (advisory.cve_id is not None and cve is None):
            invalid_alerts += 1
            continue
        all_by_ghsa[ghsa].append(row)
        if alert.state == "open":
            open_by_ghsa[ghsa].append(row)
        if cve is not None:
            key = (cve, ghsa)
            all_by_cve[key].append(row)
            any_ghsa_by_cve[cve].add(ghsa)
            if alert.state == "open":
                open_by_cve[key].append(row)

    existing_rows = list(
        connection.execute(
            select(
                AlertCandidateMatch.alert_id,
                AlertCandidateMatch.candidate_id,
                DependabotAlert.state,
            )
            .join(DependabotAlert, DependabotAlert.id == AlertCandidateMatch.alert_id)
            .where(AlertCandidateMatch.organization_id == organization_id)
        )
    )
    existing = {(row.alert_id, row.candidate_id) for row in existing_rows}
    historical = sum(row.state != "open" for row in existing_rows)

    pairs: list[tuple[UUID, UUID]] = []
    pair_context: dict[tuple[UUID, UUID], tuple[Any, Any, Any, Any]] = {}
    candidate_alert_counts: Counter[UUID] = Counter()
    alert_candidate_counts: Counter[UUID] = Counter()
    reasons: Counter[str] = Counter()
    samples: dict[str, list[dict[str, object]]] = {
        "matched": [],
        "unmatched": [],
        "ambiguous": [],
        "excluded": [],
    }

    for candidate in candidates:
        ghsa = normalize_ghsa(candidate.ghsa_id)
        cve = normalize_cve(candidate.cve_id)
        matched_rows: list[Any] = []
        all_rows: list[Any] = []
        related_rows: list[Any] = []
        reason: str | None = None

        if candidate.subject_type == "CVE":
            if cve is None or ghsa is None:
                reason = "invalid_identifier"
            else:
                key = (cve, ghsa)
                matched_rows = open_by_cve.get(key, [])
                all_rows = all_by_cve.get(key, [])
                if not matched_rows:
                    if all_rows:
                        reason = "no_open_alert"
                    elif cve in any_ghsa_by_cve:
                        reason = "cve_ghsa_conflict"
                        related_rows = [
                            row
                            for key, rows in all_by_cve.items()
                            if key[0] == cve
                            for row in rows
                        ]
                    else:
                        reason = "identifier_not_found"
        elif candidate.subject_type == "GHSA":
            if ghsa is None:
                reason = "invalid_identifier"
            else:
                matched_rows = open_by_ghsa.get(ghsa, [])
                all_rows = all_by_ghsa.get(ghsa, [])
                if not matched_rows:
                    reason = "no_open_alert" if all_rows else "identifier_not_found"
        else:
            reason = "invalid_identifier"

        if reason is not None:
            reasons[reason] += 1
            category = "ambiguous" if reason == "cve_ghsa_conflict" else "unmatched"
            if reason in {"invalid_identifier", "no_open_alert"}:
                category = "excluded"
            if len(samples[category]) < SAMPLE_LIMIT:
                source_rows = all_rows or related_rows
                if source_rows:
                    alert, advisory, repository = source_rows[0]
                    sample = _match_trace(
                        candidate, alert, advisory, repository, deliveries
                    )
                else:
                    sample = _candidate_trace(candidate, deliveries)
                samples[category].append({**sample, "reason": reason})
            continue

        for alert, advisory, repository in matched_rows:
            pair = (alert.id, candidate.id)
            pairs.append(pair)
            pair_context[pair] = (candidate, alert, advisory, repository)
            candidate_alert_counts[candidate.id] += 1
            alert_candidate_counts[alert.id] += 1

    new_pairs = [pair for pair in pairs if pair not in existing]
    for pair in pairs[:SAMPLE_LIMIT]:
        candidate, alert, advisory, repository = pair_context[pair]
        samples["matched"].append(
            _match_trace(candidate, alert, advisory, repository, deliveries)
        )

    one_to_one = sum(
        candidate_alert_counts[candidate_id] == 1
        and alert_candidate_counts[alert_id] == 1
        for alert_id, candidate_id in pairs
    )
    one_to_many = sum(count > 1 for count in candidate_alert_counts.values())
    many_to_one = sum(count > 1 for count in alert_candidate_counts.values())

    return (
        {
            "inputs": {
                "candidate_count": len(candidates),
                "alert_count": len(alert_rows),
                "alert_states": dict(sorted(alert_states.items())),
            },
            "matches": {
                "total": len(pairs),
                "new": len(new_pairs),
                "existing": len(pairs) - len(new_pairs),
                "retained_historical": historical,
                "one_to_one": one_to_one,
                "one_to_many_candidates": one_to_many,
                "many_to_one_alerts": many_to_one,
            },
            "excluded": {
                "candidate_count": sum(reasons.values()),
                "reasons": dict(sorted(reasons.items())),
                "invalid_alert_count": invalid_alerts,
                "non_open_alert_count": sum(
                    count for state, count in alert_states.items() if state != "open"
                ),
            },
            "samples": samples,
        },
        new_pairs,
    )


def run_matching(
    database_url: str,
    organization_id: UUID,
    *,
    dry_run: bool = False,
    matched_at: datetime | None = None,
    engine: Engine | None = None,
) -> dict[str, object]:
    owns_engine = engine is None
    database_engine = engine or create_engine(database_url, pool_pre_ping=True)
    timestamp = matched_at or datetime.now(UTC)
    try:
        with Session(database_engine) as session, session.begin():
            locked = session.scalar(
                text("SELECT pg_try_advisory_xact_lock(:lock_key)"),
                {"lock_key": LOCK_KEY},
            )
            if not locked:
                raise MatchingError(
                    "matching_already_running",
                    "다른 Alert–Candidate 매칭 작업이 실행 중입니다.",
                )
            organization_exists = session.scalar(
                select(Organization.id).where(Organization.id == organization_id)
            )
            if organization_exists is None:
                raise MatchingError(
                    "organization_not_found",
                    "매칭 대상 조직이 존재하지 않습니다.",
                    organization_id=str(organization_id),
                )

            result, new_pairs = _calculate(session, organization_id)
            inserted = 0
            if not dry_run and new_pairs:
                statement = insert(AlertCandidateMatch).values(
                    [
                        {
                            "organization_id": organization_id,
                            "alert_id": alert_id,
                            "candidate_id": candidate_id,
                            "matched_at": timestamp,
                        }
                        for alert_id, candidate_id in new_pairs
                    ]
                )
                statement = statement.on_conflict_do_nothing(
                    index_elements=["alert_id", "candidate_id"]
                ).returning(AlertCandidateMatch.alert_id)
                inserted = len(session.execute(statement).all())
            result["matches"]["inserted"] = inserted  # type: ignore[index]
            result["organization_id"] = str(organization_id)
            result["dry_run"] = dry_run
            result["db_applied"] = not dry_run
            return result
    finally:
        if owns_engine:
            database_engine.dispose()
