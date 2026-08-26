from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select, text
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
from watchback_backend.case_generation import __main__ as case_generation_cli
from watchback_backend.case_generation.service import (
    LOCK_KEY as CASE_GENERATION_LOCK_KEY,
    CaseGenerationError,
    run_case_generation,
)
from watchback_backend.matching.service import (
    LOCK_KEY,
    MatchingError,
    normalize_cve,
    normalize_ghsa,
    run_matching,
)
from watchback_backend.matching import __main__ as matching_cli


def _alert(
    *,
    organization_id,
    repository_id,
    advisory_id,
    number: int,
    manifest: str,
    state: str = "open",
) -> DependabotAlert:
    now = datetime(2026, 8, 26, tzinfo=UTC)
    return DependabotAlert(
        organization_id=organization_id,
        repository_id=repository_id,
        advisory_id=advisory_id,
        github_alert_number=number,
        state=state,
        package_name="example-package",
        ecosystem="npm",
        manifest_path=manifest,
        dependency_scope="runtime",
        dependency_relationship="direct",
        vulnerable_version_range="< 2.0.0",
        first_patched_version="2.0.0",
        html_url=f"https://github.com/example/repo/security/dependabot/{number}",
        github_created_at=now,
        github_updated_at=now,
        fixed_at=now if state == "fixed" else None,
        last_synced_at=now,
    )


@pytest.fixture
def matching_data(postgres_engine):
    now = datetime(2026, 8, 26, tzinfo=UTC)
    organization = Organization(
        github_organization_id=91001,
        github_login="matching-org",
        display_name="Matching Org",
    )
    other_organization = Organization(
        github_organization_id=91002,
        github_login="other-matching-org",
        display_name="Other Matching Org",
    )
    with Session(postgres_engine, expire_on_commit=False) as session:
        session.add_all([organization, other_organization])
        session.flush()
        repository = Repository(
            organization_id=organization.id,
            github_repository_id=92001,
            full_name="matching-org/service",
            display_name="matching-org/service",
            importance="critical",
            last_synced_at=now,
        )
        other_repository = Repository(
            organization_id=other_organization.id,
            github_repository_id=92002,
            full_name="other-matching-org/service",
            display_name="other-matching-org/service",
            importance="high",
            last_synced_at=now,
        )
        advisories = {
            "exact": SecurityAdvisory(
                ghsa_id="GHSA-AAAA-BBBB-CCCC",
                cve_id="CVE-2026-1001",
                summary="Exact advisory",
                severity="critical",
                github_updated_at=now,
            ),
            "other_ghsa": SecurityAdvisory(
                ghsa_id="GHSA-DDDD-EEEE-FFFF",
                cve_id="CVE-2026-1001",
                summary="Same CVE, different GHSA",
                severity="high",
                github_updated_at=now,
            ),
            "ghsa_only": SecurityAdvisory(
                ghsa_id="GHSA-GGGG-HHHH-IIII",
                cve_id=None,
                summary="GHSA only advisory",
                severity="high",
                github_updated_at=now,
            ),
            "closed_only": SecurityAdvisory(
                ghsa_id="GHSA-JJJJ-KKKK-LLLL",
                cve_id=None,
                summary="Closed only advisory",
                severity="medium",
                github_updated_at=now,
            ),
        }
        session.add_all([repository, other_repository, *advisories.values()])
        session.flush()

        alerts = [
            _alert(
                organization_id=organization.id,
                repository_id=repository.id,
                advisory_id=advisories["exact"].id,
                number=1,
                manifest="package-lock.json",
            ),
            _alert(
                organization_id=organization.id,
                repository_id=repository.id,
                advisory_id=advisories["exact"].id,
                number=2,
                manifest="examples/package-lock.json",
            ),
            _alert(
                organization_id=organization.id,
                repository_id=repository.id,
                advisory_id=advisories["ghsa_only"].id,
                number=3,
                manifest="package-lock.json",
            ),
            _alert(
                organization_id=organization.id,
                repository_id=repository.id,
                advisory_id=advisories["other_ghsa"].id,
                number=4,
                manifest="package-lock.json",
            ),
            _alert(
                organization_id=organization.id,
                repository_id=repository.id,
                advisory_id=advisories["closed_only"].id,
                number=5,
                manifest="package-lock.json",
                state="fixed",
            ),
            _alert(
                organization_id=organization.id,
                repository_id=repository.id,
                advisory_id=advisories["exact"].id,
                number=6,
                manifest="old/package-lock.json",
                state="fixed",
            ),
            _alert(
                organization_id=other_organization.id,
                repository_id=other_repository.id,
                advisory_id=advisories["exact"].id,
                number=1,
                manifest="package-lock.json",
            ),
        ]
        session.add_all(alerts)

        candidates = [
            RiskCandidate(
                source_candidate_id="candidate-cve-1",
                subject_type="CVE",
                subject_id="CVE-2026-1001",
                ghsa_id="GHSA-AAAA-BBBB-CCCC",
                cve_id="CVE-2026-1001",
                priority="P0",
                change_type="epss_spike",
                reason_summary="First CVE change",
                selected_at=now,
            ),
            RiskCandidate(
                source_candidate_id="candidate-cve-2",
                subject_type="CVE",
                subject_id=" cve-2026-1001 ",
                ghsa_id=" ghsa-aaaa-bbbb-cccc ",
                cve_id=" cve-2026-1001 ",
                priority="P1",
                change_type="kev_added",
                reason_summary="Second CVE change",
                selected_at=now + timedelta(minutes=1),
            ),
            RiskCandidate(
                source_candidate_id="candidate-ghsa",
                subject_type="GHSA",
                subject_id="GHSA-GGGG-HHHH-IIII",
                ghsa_id="GHSA-GGGG-HHHH-IIII",
                cve_id=None,
                priority="P1",
                change_type="advisory_changed",
                reason_summary="GHSA-only change",
                selected_at=now + timedelta(minutes=2),
            ),
            RiskCandidate(
                source_candidate_id="candidate-conflict",
                subject_type="CVE",
                subject_id="CVE-2026-1001",
                ghsa_id="GHSA-MMMM-NNNN-OOOO",
                cve_id="CVE-2026-1001",
                priority="P2",
                change_type="epss_spike",
                reason_summary="Conflicting identifiers",
                selected_at=now + timedelta(minutes=3),
            ),
            RiskCandidate(
                source_candidate_id="candidate-missing",
                subject_type="GHSA",
                subject_id="GHSA-PPPP-QQQQ-RRRR",
                ghsa_id="GHSA-PPPP-QQQQ-RRRR",
                cve_id=None,
                priority="P2",
                change_type="epss_spike",
                reason_summary="Missing identifier",
                selected_at=now + timedelta(minutes=4),
            ),
            RiskCandidate(
                source_candidate_id="candidate-invalid",
                subject_type="CVE",
                subject_id="not-a-cve",
                ghsa_id="not-a-ghsa",
                cve_id="not-a-cve",
                priority="P3",
                change_type="epss_spike",
                reason_summary="Invalid identifiers",
                selected_at=now + timedelta(minutes=5),
            ),
            RiskCandidate(
                source_candidate_id="candidate-closed",
                subject_type="GHSA",
                subject_id="GHSA-JJJJ-KKKK-LLLL",
                ghsa_id="GHSA-JJJJ-KKKK-LLLL",
                cve_id=None,
                priority="P3",
                change_type="epss_spike",
                reason_summary="Only closed alerts",
                selected_at=now + timedelta(minutes=6),
            ),
        ]
        batch = GoldBatch(
            source_batch_id="matching-batch",
            ds_run_id="matching-run",
            as_of=now,
            source_generated_at=now,
            policy_version="ver.1",
            schema_version="1.0",
            candidate_count=len(candidates),
            synced_at=now,
        )
        session.add_all([batch, *candidates])
        session.flush()
        session.add_all(
            GoldBatchCandidate(
                batch_id=batch.id,
                candidate_id=candidate.id,
                payload_hash=f"{index:064x}",
                received_at=now,
            )
            for index, candidate in enumerate(candidates, start=1)
        )
        session.flush()
        session.add(
            AlertCandidateMatch(
                organization_id=organization.id,
                alert_id=alerts[5].id,
                candidate_id=candidates[0].id,
                matched_at=now - timedelta(days=1),
            )
        )
        session.commit()

    batches = [batch]

    yield {
        "organization_id": organization.id,
        "other_organization_id": other_organization.id,
        "candidate_ids": [candidate.id for candidate in candidates],
        "candidates": candidates,
        "batches": batches,
        "alerts": alerts,
        "historical_match": (alerts[5].id, candidates[0].id),
    }

    tables = {
        table.name: table
        for table in [
            ReviewActivity.__table__,
            ReviewCase.__table__,
            AlertCandidateMatch.__table__,
            GoldBatchCandidate.__table__,
            RiskCandidate.__table__,
            GoldBatch.__table__,
            DependabotAlert.__table__,
            Repository.__table__,
            SecurityAdvisory.__table__,
            Organization.__table__,
        ]
    }
    with postgres_engine.begin() as connection:
        connection.execute(
            delete(tables["review_activities"]).where(
                tables["review_activities"].c.organization_id.in_(
                    [organization.id, other_organization.id]
                )
            )
        )
        connection.execute(
            delete(tables["review_cases"]).where(
                tables["review_cases"].c.organization_id.in_(
                    [organization.id, other_organization.id]
                )
            )
        )
        connection.execute(
            delete(tables["alert_candidate_matches"]).where(
                tables["alert_candidate_matches"].c.organization_id.in_(
                    [organization.id, other_organization.id]
                )
            )
        )
        connection.execute(
            delete(tables["gold_batch_candidates"]).where(
                tables["gold_batch_candidates"].c.candidate_id.in_(
                    [candidate.id for candidate in candidates]
                )
            )
        )
        connection.execute(
            delete(tables["risk_candidates"]).where(
                tables["risk_candidates"].c.id.in_(
                    [candidate.id for candidate in candidates]
                )
            )
        )
        connection.execute(
            delete(tables["gold_batches"]).where(
                tables["gold_batches"].c.id.in_([item.id for item in batches])
            )
        )
        connection.execute(
            delete(tables["dependabot_alerts"]).where(
                tables["dependabot_alerts"].c.organization_id.in_(
                    [organization.id, other_organization.id]
                )
            )
        )
        connection.execute(
            delete(tables["repositories"]).where(
                tables["repositories"].c.organization_id.in_(
                    [organization.id, other_organization.id]
                )
            )
        )
        connection.execute(
            delete(tables["security_advisories"]).where(
                tables["security_advisories"].c.id.in_(
                    [advisory.id for advisory in advisories.values()]
                )
            )
        )
        connection.execute(
            delete(tables["organizations"]).where(
                tables["organizations"].c.id.in_(
                    [organization.id, other_organization.id]
                )
            )
        )


def test_identifier_normalization() -> None:
    assert normalize_cve(" cve-2026-1001 ") == "CVE-2026-1001"
    assert normalize_ghsa(" ghsa-aaaa-bbbb-cccc ") == "GHSA-AAAA-BBBB-CCCC"
    assert normalize_cve("CVE-invalid") is None
    assert normalize_ghsa("GHSA-invalid") is None


def test_matching_is_scoped_dry_run_idempotent_and_preserves_history(
    postgres_engine, matching_data
) -> None:
    organization_id = matching_data["organization_id"]
    dry_run = run_matching("", organization_id, dry_run=True, engine=postgres_engine)

    assert dry_run["inputs"] == {
        "candidate_count": 7,
        "alert_count": 6,
        "alert_states": {"fixed": 2, "open": 4},
    }
    assert dry_run["matches"] == {
        "total": 5,
        "new": 5,
        "existing": 0,
        "retained_historical": 1,
        "one_to_one": 1,
        "one_to_many_candidates": 2,
        "many_to_one_alerts": 2,
        "inserted": 0,
    }
    assert dry_run["excluded"]["reasons"] == {
        "cve_ghsa_conflict": 1,
        "identifier_not_found": 1,
        "invalid_identifier": 1,
        "no_open_alert": 1,
    }
    assert dry_run["excluded"]["non_open_alert_count"] == 2
    assert dry_run["samples"]["ambiguous"][0]["alert_number"] == 1
    assert any(
        sample.get("alert_state") == "fixed"
        for sample in dry_run["samples"]["excluded"]
    )
    assert dry_run["samples"]["matched"][0]["batches"] == [
        {"batch_id": "matching-batch", "as_of": "2026-08-26T00:00:00+00:00"}
    ]

    with postgres_engine.connect() as connection:
        assert (
            connection.scalar(select(func.count()).select_from(AlertCandidateMatch))
            == 1
        )

    applied = run_matching("", organization_id, engine=postgres_engine)
    assert applied["matches"]["inserted"] == 5
    assert applied["db_applied"] is True

    with postgres_engine.connect() as connection:
        matched_at_before_rerun = {
            (row.alert_id, row.candidate_id): row.matched_at
            for row in connection.execute(
                select(
                    AlertCandidateMatch.alert_id,
                    AlertCandidateMatch.candidate_id,
                    AlertCandidateMatch.matched_at,
                ).where(AlertCandidateMatch.organization_id == organization_id)
            )
        }
        assert connection.scalar(select(func.count()).select_from(ReviewCase)) == 0

    rerun = run_matching("", organization_id, engine=postgres_engine)
    assert rerun["matches"]["new"] == 0
    assert rerun["matches"]["existing"] == 5
    assert rerun["matches"]["inserted"] == 0
    assert rerun["matches"]["retained_historical"] == 1

    with postgres_engine.connect() as connection:
        organization_matches = connection.scalar(
            select(func.count())
            .select_from(AlertCandidateMatch)
            .where(AlertCandidateMatch.organization_id == organization_id)
        )
        other_matches = connection.scalar(
            select(func.count())
            .select_from(AlertCandidateMatch)
            .where(
                AlertCandidateMatch.organization_id
                == matching_data["other_organization_id"]
            )
        )
        matched_at_after_rerun = {
            (row.alert_id, row.candidate_id): row.matched_at
            for row in connection.execute(
                select(
                    AlertCandidateMatch.alert_id,
                    AlertCandidateMatch.candidate_id,
                    AlertCandidateMatch.matched_at,
                ).where(AlertCandidateMatch.organization_id == organization_id)
            )
        }
        assert organization_matches == 6
        assert other_matches == 0
        assert matched_at_after_rerun == matched_at_before_rerun


def test_case_generation_updates_open_case_and_reopens_resolved_case(
    postgres_engine, matching_data
) -> None:
    organization_id = matching_data["organization_id"]
    initial_time = datetime(2026, 8, 26, 1, tzinfo=UTC)
    run_matching("", organization_id, matched_at=initial_time, engine=postgres_engine)

    initial = run_case_generation(
        "", organization_id, occurred_at=initial_time, engine=postgres_engine
    )
    assert initial["cases"] == {
        "created": 3,
        "updated": 0,
        "reopened": 0,
        "unchanged": 0,
        "excluded": 0,
    }
    assert initial["excluded"]["non_open_alert_count"] == 1

    alert_one, alert_two = matching_data["alerts"][:2]
    representative = matching_data["candidates"][1]
    resolution_time = initial_time + timedelta(hours=1)
    with Session(postgres_engine) as session:
        resolved_case = session.scalar(
            select(ReviewCase).where(ReviewCase.alert_id == alert_one.id)
        )
        assert resolved_case is not None
        resolved_case.status = "resolved"
        resolved_case.resolved_at = resolution_time
        resolved_case.updated_at = resolution_time
        original_batch_id = resolved_case.representative_batch_id
        session.commit()

    repeated_batch = GoldBatch(
        source_batch_id="matching-batch-redelivery",
        ds_run_id="matching-run-redelivery",
        as_of=resolution_time,
        source_generated_at=resolution_time,
        policy_version="ver.1",
        schema_version="1.0",
        candidate_count=1,
        synced_at=resolution_time,
    )
    with Session(postgres_engine, expire_on_commit=False) as session:
        session.add(repeated_batch)
        session.flush()
        session.add(
            GoldBatchCandidate(
                batch_id=repeated_batch.id,
                candidate_id=representative.id,
                payload_hash="f" * 64,
                received_at=resolution_time,
            )
        )
        session.commit()
    matching_data["batches"].append(repeated_batch)

    redelivery = run_case_generation(
        "",
        organization_id,
        occurred_at=resolution_time + timedelta(minutes=1),
        engine=postgres_engine,
    )
    assert redelivery["cases"] == {
        "created": 0,
        "updated": 1,
        "reopened": 0,
        "unchanged": 2,
        "excluded": 0,
    }
    with Session(postgres_engine) as session:
        resolved_case = session.scalar(
            select(ReviewCase).where(ReviewCase.alert_id == alert_one.id)
        )
        open_case = session.scalar(
            select(ReviewCase).where(ReviewCase.alert_id == alert_two.id)
        )
        assert resolved_case is not None and open_case is not None
        assert resolved_case.status == "resolved"
        assert resolved_case.representative_batch_id == original_batch_id
        assert open_case.representative_batch_id == repeated_batch.id
        assert (
            session.scalar(
                select(func.count())
                .select_from(ReviewActivity)
                .where(ReviewActivity.organization_id == organization_id)
            )
            == 3
        )

    new_candidate = RiskCandidate(
        source_candidate_id="candidate-cve-new-change",
        subject_type="CVE",
        subject_id="CVE-2026-1001",
        ghsa_id="GHSA-AAAA-BBBB-CCCC",
        cve_id="CVE-2026-1001",
        priority="P0",
        change_type="kev_added",
        reason_summary="새로운 KEV 변화",
        selected_at=resolution_time + timedelta(hours=1),
    )
    new_batch = GoldBatch(
        source_batch_id="matching-batch-new-change",
        ds_run_id="matching-run-new-change",
        as_of=resolution_time + timedelta(hours=1),
        source_generated_at=resolution_time + timedelta(hours=1),
        policy_version="ver.2",
        schema_version="1.0",
        candidate_count=1,
        synced_at=resolution_time + timedelta(hours=1),
    )
    with Session(postgres_engine, expire_on_commit=False) as session:
        session.add_all([new_candidate, new_batch])
        session.flush()
        session.add(
            GoldBatchCandidate(
                batch_id=new_batch.id,
                candidate_id=new_candidate.id,
                payload_hash="e" * 64,
                received_at=resolution_time + timedelta(hours=1),
            )
        )
        session.add_all(
            [
                AlertCandidateMatch(
                    organization_id=organization_id,
                    alert_id=alert_one.id,
                    candidate_id=new_candidate.id,
                    matched_at=resolution_time + timedelta(hours=1),
                ),
                AlertCandidateMatch(
                    organization_id=organization_id,
                    alert_id=alert_two.id,
                    candidate_id=new_candidate.id,
                    matched_at=resolution_time + timedelta(hours=1),
                ),
            ]
        )
        session.commit()
    matching_data["candidates"].append(new_candidate)
    matching_data["batches"].append(new_batch)

    changed = run_case_generation(
        "",
        organization_id,
        occurred_at=resolution_time + timedelta(hours=2),
        engine=postgres_engine,
    )
    assert changed["cases"] == {
        "created": 0,
        "updated": 1,
        "reopened": 1,
        "unchanged": 1,
        "excluded": 0,
    }
    with Session(postgres_engine) as session:
        resolved_case = session.scalar(
            select(ReviewCase).where(ReviewCase.alert_id == alert_one.id)
        )
        assert resolved_case is not None
        assert resolved_case.status == "open"
        assert resolved_case.resolved_at is None
        assert resolved_case.reopened_count == 1
        assert resolved_case.representative_candidate_id == new_candidate.id
        assert resolved_case.representative_batch_id == new_batch.id
        assert resolved_case.review_reason == "새로운 KEV 변화"
        assert (
            session.scalar(
                select(func.count())
                .select_from(ReviewActivity)
                .where(
                    ReviewActivity.organization_id == organization_id,
                    ReviewActivity.activity_type == "case_reopened",
                )
            )
            == 1
        )


def test_concurrent_matching_is_rejected_without_writes(
    postgres_engine, matching_data
) -> None:
    with postgres_engine.connect() as lock_connection:
        transaction = lock_connection.begin()
        lock_connection.execute(
            text("SELECT pg_advisory_xact_lock(:lock_key)"), {"lock_key": LOCK_KEY}
        )
        try:
            with pytest.raises(MatchingError, match="다른 Alert–Candidate") as exc_info:
                run_matching(
                    "",
                    matching_data["organization_id"],
                    engine=postgres_engine,
                )
            assert exc_info.value.code == "matching_already_running"
        finally:
            transaction.rollback()

    with postgres_engine.connect() as connection:
        assert (
            connection.scalar(select(func.count()).select_from(AlertCandidateMatch))
            == 1
        )


def test_unknown_organization_is_rejected(postgres_engine) -> None:
    with pytest.raises(MatchingError, match="조직이 존재하지") as exc_info:
        run_matching("", uuid4(), engine=postgres_engine)
    assert exc_info.value.code == "organization_not_found"


def test_concurrent_case_generation_is_rejected_without_writes(
    postgres_engine, matching_data
) -> None:
    run_matching("", matching_data["organization_id"], engine=postgres_engine)
    with postgres_engine.connect() as lock_connection:
        transaction = lock_connection.begin()
        lock_connection.execute(
            text("SELECT pg_advisory_xact_lock(:lock_key)"),
            {"lock_key": CASE_GENERATION_LOCK_KEY},
        )
        try:
            with pytest.raises(CaseGenerationError, match="다른 재검토 Case"):
                run_case_generation(
                    "", matching_data["organization_id"], engine=postgres_engine
                )
        finally:
            transaction.rollback()

    with postgres_engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(ReviewCase)) == 0


def test_cli_requires_configuration(monkeypatch, capsys) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("ORGANIZATION_ID", raising=False)

    assert matching_cli.main(["--dry-run"]) == 1
    output = capsys.readouterr().out
    assert '"code": "configuration_error"' in output
    assert '"db_applied": false' in output


def test_cli_passes_dry_run_and_prints_one_json(monkeypatch, capsys) -> None:
    organization_id = uuid4()
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://example")
    monkeypatch.setenv("ORGANIZATION_ID", str(organization_id))
    received = {}

    def fake_run(database_url, requested_organization_id, *, dry_run):
        received.update(
            database_url=database_url,
            organization_id=requested_organization_id,
            dry_run=dry_run,
        )
        return {"organization_id": str(requested_organization_id), "db_applied": False}

    monkeypatch.setattr(matching_cli, "run_matching", fake_run)

    assert matching_cli.main(["--dry-run"]) == 0
    output = capsys.readouterr().out.strip().splitlines()
    assert len(output) == 1
    assert '"success": true' in output[0]
    assert received == {
        "database_url": "postgresql+psycopg://example",
        "organization_id": organization_id,
        "dry_run": True,
    }


def test_case_generation_cli_requires_configuration(monkeypatch, capsys) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("ORGANIZATION_ID", raising=False)

    assert case_generation_cli.main(["--dry-run"]) == 1
    output = capsys.readouterr().out
    assert '"code": "configuration_error"' in output
    assert '"db_applied": false' in output


def test_case_generation_cli_passes_dry_run(monkeypatch, capsys) -> None:
    organization_id = uuid4()
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://example")
    monkeypatch.setenv("ORGANIZATION_ID", str(organization_id))
    received = {}

    def fake_run(database_url, requested_organization_id, *, dry_run):
        received.update(
            database_url=database_url,
            organization_id=requested_organization_id,
            dry_run=dry_run,
        )
        return {"organization_id": str(requested_organization_id), "db_applied": False}

    monkeypatch.setattr(case_generation_cli, "run_case_generation", fake_run)

    assert case_generation_cli.main(["--dry-run"]) == 0
    assert len(capsys.readouterr().out.strip().splitlines()) == 1
    assert received == {
        "database_url": "postgresql+psycopg://example",
        "organization_id": organization_id,
        "dry_run": True,
    }
