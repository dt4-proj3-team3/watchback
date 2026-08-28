from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from watchback_backend.api.service import RequestContext, get_review_case
from watchback_backend.db.models import (
    AlertCandidateMatch,
    CandidateEvidence,
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
from watchback_backend.case_generation.service import run_case_generation
from watchback_backend.matching.service import run_matching


REPOSITORY_ROOT = Path(__file__).parents[3]
VULNERABILITIES_PATH = REPOSITORY_ROOT / "data/demo/vulnerabilities.json"
REVIEW_CASES_PATH = REPOSITORY_ROOT / "data/demo/review-cases.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _timestamp(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


@pytest.fixture
def demo_matching_data(postgres_engine):
    vulnerability_fixture = _read_json(VULNERABILITIES_PATH)
    review_fixture = _read_json(REVIEW_CASES_PATH)
    captured_at = _timestamp(vulnerability_fixture["captured_at"])
    assert captured_at is not None

    organization = Organization(
        github_organization_id=93001,
        github_login="novalink-matching-integration",
        display_name="노바링크 매칭 통합 테스트",
    )

    with Session(postgres_engine, expire_on_commit=False) as session:
        session.add(organization)
        session.flush()

        repositories: dict[str, Repository] = {}
        for source_repository in vulnerability_fixture["repositories"]:
            full_name = source_repository["full_name"]
            display_name = next(
                item["repository"]["display_name"]
                for item in review_fixture["list"]["items"]
                if item["repository"]["full_name"] == full_name
            )
            repository = Repository(
                organization_id=organization.id,
                github_repository_id=source_repository["id"],
                full_name=full_name,
                display_name=display_name,
                default_branch=source_repository["default_branch"],
                importance="critical",
                github_updated_at=_timestamp(source_repository["commit_at"]),
                last_synced_at=captured_at,
            )
            repositories[full_name] = repository
            session.add(repository)

        advisories: dict[str, SecurityAdvisory] = {}
        for vulnerability in vulnerability_fixture["vulnerabilities"]:
            advisory = SecurityAdvisory(
                ghsa_id=vulnerability["ghsa_id"],
                cve_id=vulnerability["cve_id"],
                summary=vulnerability["summary"],
                severity=vulnerability["severity"],
                cvss_score=vulnerability["cvss_score"],
                github_published_at=_timestamp(vulnerability["advisory_published_at"]),
                github_updated_at=_timestamp(vulnerability["advisory_updated_at"]),
                github_withdrawn_at=_timestamp(vulnerability["advisory_withdrawn_at"]),
            )
            advisories[vulnerability["ghsa_id"]] = advisory
            session.add(advisory)

        session.flush()

        for vulnerability in vulnerability_fixture["vulnerabilities"]:
            advisory = advisories[vulnerability["ghsa_id"]]
            for source_alert in vulnerability["alerts"]:
                repository = repositories[source_alert["repository"]]
                session.add(
                    DependabotAlert(
                        organization_id=organization.id,
                        repository_id=repository.id,
                        advisory_id=advisory.id,
                        github_alert_number=source_alert["alert_number"],
                        state=source_alert["state"],
                        package_name=vulnerability["package"],
                        ecosystem=vulnerability["ecosystem"],
                        manifest_path=source_alert["manifest_path"],
                        dependency_scope=source_alert["scope"],
                        dependency_relationship=source_alert["relationship"],
                        vulnerable_version_range=source_alert[
                            "vulnerable_version_range"
                        ],
                        first_patched_version=source_alert["first_patched_version"],
                        html_url=source_alert["html_url"],
                        github_created_at=_timestamp(source_alert["alert_created_at"]),
                        github_updated_at=_timestamp(source_alert["alert_updated_at"]),
                        dismissed_at=_timestamp(source_alert["dismissed_at"]),
                        fixed_at=_timestamp(source_alert["fixed_at"]),
                        auto_dismissed_at=_timestamp(source_alert["auto_dismissed_at"]),
                        last_synced_at=captured_at,
                    )
                )

        source_candidates = {
            candidate["source_candidate_id"]: candidate
            for detail in review_fixture["details"].values()
            for candidate in detail["candidates"]
        }
        candidate_rows: dict[str, RiskCandidate] = {}
        batch_ids: list[UUID] = []
        candidate_ids: list[UUID] = []

        for source_candidate_id, source_candidate in source_candidates.items():
            candidate = RiskCandidate(
                id=UUID(source_candidate["id"]),
                source_candidate_id=source_candidate_id,
                subject_type=source_candidate["subject_type"],
                subject_id=source_candidate["subject_id"],
                ghsa_id=source_candidate["ghsa_id"],
                cve_id=source_candidate["cve_id"],
                priority=source_candidate["priority"],
                change_type=source_candidate["change_type"],
                reason_summary=source_candidate["reason_summary"],
                selected_at=_timestamp(source_candidate["selected_at"]),
            )
            candidate_rows[source_candidate_id] = candidate
            candidate_ids.append(candidate.id)
            session.add(candidate)

        session.flush()

        for source_candidate_id, source_candidate in source_candidates.items():
            candidate = candidate_rows[source_candidate_id]
            for delivery in source_candidate["deliveries"]:
                batch_id = UUID(delivery["batch_id"])
                batch_ids.append(batch_id)
                session.add(
                    GoldBatch(
                        id=batch_id,
                        source_batch_id=delivery["source_batch_id"],
                        ds_run_id=f"demo-{delivery['source_batch_id']}",
                        as_of=_timestamp(delivery["as_of"]),
                        source_generated_at=_timestamp(delivery["source_generated_at"]),
                        policy_version=delivery["policy_version"],
                        schema_version=delivery["schema_version"],
                        candidate_count=1,
                        synced_at=_timestamp(delivery["received_at"]),
                    )
                )
                session.add(
                    GoldBatchCandidate(
                        batch_id=batch_id,
                        candidate_id=candidate.id,
                        payload_hash=hashlib.sha256(
                            source_candidate_id.encode("utf-8")
                        ).hexdigest(),
                        received_at=_timestamp(delivery["received_at"]),
                    )
                )

        session.flush()

        for source_candidate_id, source_candidate in source_candidates.items():
            candidate = candidate_rows[source_candidate_id]
            for evidence in source_candidate["evidence"]:
                session.add(
                    CandidateEvidence(
                        id=UUID(evidence["id"]),
                        source_evidence_id=evidence["source_evidence_id"],
                        batch_id=UUID(evidence["batch_id"]),
                        candidate_id=candidate.id,
                        signal=evidence["signal"],
                        value_type=evidence["value_type"],
                        previous_value=evidence["previous_value"],
                        current_value=evidence["current_value"],
                        observed_at=_timestamp(evidence["observed_at"]),
                        source=evidence["source"],
                        evidence_summary=evidence["evidence_summary"],
                    )
                )

        session.commit()

    yield {
        "organization_id": organization.id,
        "vulnerability_fixture": vulnerability_fixture,
        "review_fixture": review_fixture,
        "candidate_ids": candidate_ids,
        "batch_ids": batch_ids,
        "advisory_ids": [advisory.id for advisory in advisories.values()],
    }

    with postgres_engine.begin() as connection:
        connection.execute(
            delete(ReviewActivity).where(
                ReviewActivity.organization_id == organization.id
            )
        )
        connection.execute(
            delete(ReviewCase).where(ReviewCase.organization_id == organization.id)
        )
        connection.execute(
            delete(AlertCandidateMatch).where(
                AlertCandidateMatch.organization_id == organization.id
            )
        )
        connection.execute(
            delete(CandidateEvidence).where(
                CandidateEvidence.candidate_id.in_(candidate_ids)
            )
        )
        connection.execute(
            delete(GoldBatchCandidate).where(
                GoldBatchCandidate.candidate_id.in_(candidate_ids)
            )
        )
        connection.execute(
            delete(RiskCandidate).where(RiskCandidate.id.in_(candidate_ids))
        )
        connection.execute(delete(GoldBatch).where(GoldBatch.id.in_(batch_ids)))
        connection.execute(
            delete(DependabotAlert).where(
                DependabotAlert.organization_id == organization.id
            )
        )
        connection.execute(
            delete(Repository).where(Repository.organization_id == organization.id)
        )
        connection.execute(
            delete(SecurityAdvisory).where(
                SecurityAdvisory.id.in_(
                    [advisory.id for advisory in advisories.values()]
                )
            )
        )
        connection.execute(
            delete(Organization).where(Organization.id == organization.id)
        )


def test_actual_alert_snapshot_matches_realistic_gold_fixture(
    postgres_engine, demo_matching_data
) -> None:
    organization_id = demo_matching_data["organization_id"]
    vulnerability_fixture = demo_matching_data["vulnerability_fixture"]
    review_fixture = demo_matching_data["review_fixture"]

    dry_run = run_matching("", organization_id, dry_run=True, engine=postgres_engine)

    assert dry_run["inputs"] == {
        "candidate_count": 16,
        "alert_count": 31,
        "alert_states": {"fixed": 6, "open": 25},
    }
    assert dry_run["matches"] == {
        "total": 26,
        "new": 26,
        "existing": 0,
        "retained_historical": 0,
        "one_to_one": 1,
        "one_to_many_candidates": 10,
        "many_to_one_alerts": 10,
        "inserted": 0,
    }
    assert dry_run["excluded"]["candidate_count"] == 0
    assert dry_run["excluded"]["non_open_alert_count"] == 6

    applied = run_matching("", organization_id, engine=postgres_engine)
    assert applied["matches"]["inserted"] == 26
    assert applied["db_applied"] is True

    with postgres_engine.connect() as connection:
        matched_rows = connection.execute(
            select(
                Repository.full_name,
                DependabotAlert.github_alert_number,
                DependabotAlert.state,
                DependabotAlert.manifest_path,
                DependabotAlert.package_name,
                SecurityAdvisory.cve_id,
                SecurityAdvisory.ghsa_id,
                RiskCandidate.source_candidate_id,
                RiskCandidate.change_type,
            )
            .select_from(AlertCandidateMatch)
            .join(DependabotAlert, DependabotAlert.id == AlertCandidateMatch.alert_id)
            .join(Repository, Repository.id == DependabotAlert.repository_id)
            .join(
                SecurityAdvisory,
                SecurityAdvisory.id == DependabotAlert.advisory_id,
            )
            .join(RiskCandidate, RiskCandidate.id == AlertCandidateMatch.candidate_id)
            .where(AlertCandidateMatch.organization_id == organization_id)
        ).all()
        assert connection.scalar(select(func.count()).select_from(ReviewCase)) == 0
        assert connection.scalar(select(func.count()).select_from(GoldBatch)) == 16
        assert (
            connection.scalar(select(func.count()).select_from(CandidateEvidence)) == 20
        )

    matched_pairs = {
        (row.full_name, row.github_alert_number, row.source_candidate_id)
        for row in matched_rows
    }
    source_candidates = {
        candidate["source_candidate_id"]: candidate
        for detail in review_fixture["details"].values()
        for candidate in detail["candidates"]
    }
    expected_content = {
        (
            alert["repository"],
            alert["alert_number"],
            alert["manifest_path"],
            vulnerability["package"],
            vulnerability["cve_id"],
            vulnerability["ghsa_id"],
            candidate["source_candidate_id"],
            candidate["change_type"],
        )
        for vulnerability in vulnerability_fixture["vulnerabilities"]
        for alert in vulnerability["alerts"]
        if alert["state"] == "open"
        for candidate in source_candidates.values()
        if candidate["cve_id"].strip().upper() == vulnerability["cve_id"].upper()
        and candidate["ghsa_id"].strip().upper() == vulnerability["ghsa_id"].upper()
    }
    actual_content = {
        (
            row.full_name,
            row.github_alert_number,
            row.manifest_path,
            row.package_name,
            row.cve_id,
            row.ghsa_id,
            row.source_candidate_id,
            row.change_type,
        )
        for row in matched_rows
    }
    expected_screen_pairs = {
        (
            item["repository"]["full_name"],
            item["alert"]["github_alert_number"],
            item["latest_candidate"]["source_candidate_id"],
        )
        for item in review_fixture["list"]["items"]
    }

    assert actual_content == expected_content
    assert len(expected_screen_pairs) == 10
    assert expected_screen_pairs <= matched_pairs
    assert {row.state for row in matched_rows} == {"open"}

    rerun = run_matching("", organization_id, engine=postgres_engine)
    assert rerun["matches"]["new"] == 0
    assert rerun["matches"]["existing"] == 26
    assert rerun["matches"]["inserted"] == 0


def test_demo_matches_create_one_case_per_repository_cve(
    postgres_engine, demo_matching_data
) -> None:
    organization_id = demo_matching_data["organization_id"]
    occurred_at = datetime.fromisoformat("2026-08-26T12:00:00+00:00")
    run_matching("", organization_id, engine=postgres_engine)

    dry_run = run_case_generation(
        "",
        organization_id,
        dry_run=True,
        occurred_at=occurred_at,
        engine=postgres_engine,
    )
    assert dry_run["inputs"] == {
        "match_count": 26,
        "open_alert_count": 15,
        "non_open_alert_count": 0,
        "existing_case_count": 0,
    }
    assert dry_run["cases"] == {
        "created": 9,
        "updated": 0,
        "reopened": 0,
        "unchanged": 0,
        "excluded": 0,
    }

    with postgres_engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(ReviewCase)) == 0

    applied = run_case_generation(
        "", organization_id, occurred_at=occurred_at, engine=postgres_engine
    )
    assert applied["cases"]["created"] == 9

    with Session(postgres_engine) as session:
        case_rows = session.execute(
            select(ReviewCase, DependabotAlert, SecurityAdvisory, RiskCandidate)
            .join(DependabotAlert, DependabotAlert.id == ReviewCase.alert_id)
            .join(SecurityAdvisory, SecurityAdvisory.id == DependabotAlert.advisory_id)
            .join(
                RiskCandidate,
                RiskCandidate.id == ReviewCase.representative_candidate_id,
            )
            .where(ReviewCase.organization_id == organization_id)
        ).all()
        assert len(case_rows) == 9
        assert all(
            row.ReviewCase.priority == row.SecurityAdvisory.severity
            for row in case_rows
        )
        assert all(
            row.ReviewCase.review_reason == row.RiskCandidate.reason_summary
            for row in case_rows
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(ReviewActivity)
                .where(
                    ReviewActivity.organization_id == organization_id,
                    ReviewActivity.activity_type == "case_opened",
                )
            )
            == 9
        )

        vite_case = next(
            row for row in case_rows if row.DependabotAlert.github_alert_number == 3
        )
        assert vite_case.RiskCandidate.source_candidate_id.endswith("2026-01-23")
        assert vite_case.ReviewCase.priority == "medium"
        assert vite_case.ReviewCase.representative_batch_id is not None

        case_ids_before = {row.ReviewCase.id for row in case_rows}

    rerun = run_case_generation(
        "", organization_id, occurred_at=occurred_at, engine=postgres_engine
    )
    assert rerun["cases"] == {
        "created": 0,
        "updated": 0,
        "reopened": 0,
        "unchanged": 9,
        "excluded": 0,
    }

    with Session(postgres_engine) as session:
        assert (
            set(
                session.scalars(
                    select(ReviewCase.id).where(
                        ReviewCase.organization_id == organization_id
                    )
                )
            )
            == case_ids_before
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(ReviewActivity)
                .where(ReviewActivity.organization_id == organization_id)
            )
            == 9
        )


def test_actual_alert_cases_expose_evidence_as_ordered_timeline(
    postgres_engine, demo_matching_data
) -> None:
    organization_id = demo_matching_data["organization_id"]
    occurred_at = datetime.fromisoformat("2026-08-26T12:00:00+00:00")
    run_matching("", organization_id, engine=postgres_engine)
    run_case_generation(
        "", organization_id, occurred_at=occurred_at, engine=postgres_engine
    )

    context = RequestContext(
        organization_id=organization_id,
        user_id=organization_id,
        display_name="통합 테스트 검토자",
    )
    with Session(postgres_engine) as session:
        cases_by_alert_number = {
            alert_number: case_id
            for case_id, alert_number in session.execute(
                select(ReviewCase.id, DependabotAlert.github_alert_number)
                .join(DependabotAlert, DependabotAlert.id == ReviewCase.alert_id)
                .where(
                    ReviewCase.organization_id == organization_id,
                    DependabotAlert.github_alert_number.in_([3, 4, 213]),
                )
            )
        }
        vite = get_review_case(session, context, cases_by_alert_number[3])
        annotated_vite = get_review_case(session, context, cases_by_alert_number[4])
        litellm = get_review_case(session, context, cases_by_alert_number[213])

    assert vite.alert.package_name == "vite"
    assert vite.advisory.cve_id == "CVE-2025-31125"
    assert vite.advisory.ghsa_id == "GHSA-4r4m-qw57-chr8"
    assert vite.latest_candidate.source_candidate_id.endswith("2026-01-23")
    assert [candidate.source_candidate_id for candidate in vite.candidates] == [
        "expected-cve-2025-31125-2025-05-01",
        "expected-cve-2025-31125-2026-01-22",
        "expected-cve-2025-31125-2026-01-23",
    ]
    assert [
        (
            evidence.signal,
            evidence.observed_at.date().isoformat(),
            evidence.previous_value,
            evidence.current_value,
        )
        for candidate in vite.candidates
        for evidence in candidate.evidence
    ] == [
        ("epss_score_d30", "2025-05-01", "0.00032000", "0.07669000"),
        ("kev", "2026-01-22", "false", "true"),
        ("epss_percentile_d30", "2026-01-23", "0.87421000", "0.98798000"),
    ]

    assert annotated_vite.advisory.cve_id == "CVE-2025-31486"
    assert [
        candidate.source_candidate_id for candidate in annotated_vite.candidates
    ] == [
        "expected-cve-2025-31486-2025-11-18",
        "expected-cve-2025-31486-2026-06-15",
    ]
    assert [
        (
            delivery.as_of.date().isoformat(),
            [item.annotation_type for item in delivery.source_annotations],
        )
        for candidate in annotated_vite.candidates
        for delivery in candidate.deliveries
    ] == [
        ("2025-11-18", ["EPSS_SOURCE_SCORE_SHIFT"]),
        ("2026-06-15", ["EPSS_MODEL_TRANSITION"]),
    ]
    assert [
        item.annotation_type for item in annotated_vite.source_annotations
    ] == ["EPSS_MODEL_TRANSITION"]

    assert litellm.alert.package_name == "litellm"
    assert litellm.advisory.cve_id == "CVE-2026-42208"
    assert litellm.advisory.ghsa_id == "GHSA-r75f-5x8p-qvmc"
    assert litellm.latest_candidate.source_candidate_id.endswith("2026-06-07")
    assert [candidate.source_candidate_id for candidate in litellm.candidates] == [
        "expected-cve-2026-42208-2026-05-08",
        "expected-cve-2026-42208-2026-06-07",
    ]
    litellm_timeline = [
        (
            evidence.signal,
            evidence.observed_at.date().isoformat(),
            evidence.previous_value,
            evidence.current_value,
        )
        for candidate in litellm.candidates
        for evidence in candidate.evidence
    ]
    assert litellm_timeline[0] == ("kev", "2026-05-08", "false", "true")
    assert set(litellm_timeline[1:]) == {
        ("epss_score_d30", "2026-06-07", "0.00084000", "0.56947000"),
        ("epss_percentile_d30", "2026-06-07", "0.24307000", "0.98176000"),
    }
