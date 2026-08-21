from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect, select
from sqlalchemy.exc import IntegrityError

from watchback_backend.db.models import Base


EXPECTED_TABLES = {
    "alert_candidate_matches",
    "candidate_evidence",
    "dependabot_alerts",
    "external_links",
    "gold_batch_candidates",
    "gold_batches",
    "organizations",
    "repositories",
    "review_activities",
    "review_cases",
    "risk_candidates",
    "security_advisories",
    "users",
}


@contextmanager
def expect_integrity_error(engine: Engine):
    with pytest.raises(IntegrityError), engine.begin() as connection:
        yield connection


def test_metadata_contains_the_operational_schema() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES

    alert = Base.metadata.tables["dependabot_alerts"]
    assert {column.name for column in alert.primary_key.columns} == {"id"}
    assert any(
        {column.name for column in constraint.columns}
        == {"repository_id", "github_alert_number"}
        for constraint in alert.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    )

    review_case = Base.metadata.tables["review_cases"]
    assert any(
        {column.name for column in constraint.columns} == {"alert_id"}
        for constraint in review_case.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    )

    match = Base.metadata.tables["alert_candidate_matches"]
    assert {column.name for column in match.primary_key.columns} == {
        "alert_id",
        "candidate_id",
    }

    candidate = Base.metadata.tables["risk_candidates"]
    assert "ghsa_id" not in candidate.columns
    assert "observed_at" not in candidate.columns
    assert candidate.columns["cve_id"].nullable is False
    assert any(
        index.columns.keys() == ["cve_id"] and index.unique is False
        for index in candidate.indexes
    )

    advisory = Base.metadata.tables["security_advisories"]
    assert advisory.columns["ghsa_id"].unique is True
    assert advisory.columns["cve_id"].nullable is True

    batch = Base.metadata.tables["gold_batches"]
    assert "record_count" not in batch.columns
    assert batch.columns["candidate_count"].nullable is False

    uncommented_columns = [
        f"{table.name}.{column.name}"
        for table in Base.metadata.tables.values()
        for column in table.columns
        if not column.comment
    ]
    assert uncommented_columns == []


def test_migration_is_current(postgres_engine: Engine) -> None:
    assert set(inspect(postgres_engine).get_table_names()) == EXPECTED_TABLES | {
        "alembic_version"
    }
    command.check(Config(Path(__file__).parents[1] / "alembic.ini"))


def test_repository_display_name_migration_backfills_existing_rows(
    postgres_engine: Engine,
) -> None:
    config = Config(Path(__file__).parents[1] / "alembic.ini")
    tables = Base.metadata.tables
    now = datetime.now(UTC)
    organization_id = uuid4()
    repository_id = uuid4()

    command.downgrade(config, "0001")
    try:
        with postgres_engine.begin() as connection:
            connection.execute(
                tables["organizations"].insert(),
                {
                    "id": organization_id,
                    "github_organization_id": 3001,
                    "github_login": "migration-test-org",
                    "display_name": "Migration Test",
                },
            )
            connection.execute(
                tables["repositories"].insert(),
                {
                    "id": repository_id,
                    "organization_id": organization_id,
                    "github_repository_id": 4001,
                    "full_name": "migration-test-org/example",
                    "importance": "high",
                    "last_synced_at": now,
                },
            )

        command.upgrade(config, "head")

        with postgres_engine.begin() as connection:
            display_name = connection.scalar(
                select(tables["repositories"].c.display_name).where(
                    tables["repositories"].c.id == repository_id
                )
            )
            assert display_name == "migration-test-org/example"
            connection.execute(
                tables["repositories"].delete().where(
                    tables["repositories"].c.id == repository_id
                )
            )
            connection.execute(
                tables["organizations"].delete().where(
                    tables["organizations"].c.id == organization_id
                )
            )
    finally:
        command.upgrade(config, "head")


def test_dependabot_source_enum_migration_converts_existing_values(
    postgres_engine: Engine,
) -> None:
    config = Config(Path(__file__).parents[1] / "alembic.ini")
    tables = Base.metadata.tables
    now = datetime.now(UTC)
    organization_id = uuid4()
    repository_id = uuid4()
    advisory_id = uuid4()
    alert_id = uuid4()
    auto_dismissed_alert_id = uuid4()

    command.downgrade(config, "0002")
    try:
        with postgres_engine.begin() as connection:
            connection.execute(
                tables["organizations"].insert(),
                {
                    "id": organization_id,
                    "github_organization_id": 5001,
                    "github_login": "enum-migration-org",
                    "display_name": "Enum Migration",
                },
            )
            connection.execute(
                tables["repositories"].insert(),
                {
                    "id": repository_id,
                    "organization_id": organization_id,
                    "github_repository_id": 6001,
                    "full_name": "enum-migration-org/example",
                    "display_name": "enum-migration-org/example",
                    "importance": "high",
                    "last_synced_at": now,
                },
            )
            connection.execute(
                tables["security_advisories"].insert(),
                {
                    "id": advisory_id,
                    "ghsa_id": "GHSA-enum-migration",
                    "summary": "Enum migration",
                    "severity": "moderate",
                    "github_updated_at": now,
                },
            )
            connection.execute(
                tables["dependabot_alerts"].insert(),
                {
                    "id": alert_id,
                    "organization_id": organization_id,
                    "repository_id": repository_id,
                    "advisory_id": advisory_id,
                    "github_alert_number": 1,
                    "state": "open",
                    "package_name": "example",
                    "ecosystem": "npm",
                    "dependency_relationship": "indirect",
                    "vulnerable_version_range": "< 2",
                    "html_url": (
                        "https://github.com/enum-migration-org/example/"
                        "security/dependabot/1"
                    ),
                    "github_created_at": now,
                    "github_updated_at": now,
                    "last_synced_at": now,
                },
            )

        command.upgrade(config, "0003")
        with postgres_engine.begin() as connection:
            assert connection.scalar(
                select(tables["security_advisories"].c.severity).where(
                    tables["security_advisories"].c.id == advisory_id
                )
            ) == "medium"
            assert connection.scalar(
                select(tables["dependabot_alerts"].c.dependency_relationship).where(
                    tables["dependabot_alerts"].c.id == alert_id
                )
            ) == "transitive"
            connection.execute(
                tables["dependabot_alerts"].insert(),
                {
                    "id": auto_dismissed_alert_id,
                    "organization_id": organization_id,
                    "repository_id": repository_id,
                    "advisory_id": advisory_id,
                    "github_alert_number": 2,
                    "state": "auto_dismissed",
                    "package_name": "auto-example",
                    "ecosystem": "npm",
                    "dependency_relationship": "unknown",
                    "vulnerable_version_range": "< 2",
                    "html_url": (
                        "https://github.com/enum-migration-org/example/"
                        "security/dependabot/2"
                    ),
                    "github_created_at": now,
                    "github_updated_at": now,
                    "auto_dismissed_at": now,
                    "last_synced_at": now,
                },
            )

        command.downgrade(config, "0002")
        with postgres_engine.begin() as connection:
            assert connection.scalar(
                select(tables["security_advisories"].c.severity).where(
                    tables["security_advisories"].c.id == advisory_id
                )
            ) == "moderate"
            assert connection.scalar(
                select(tables["dependabot_alerts"].c.dependency_relationship).where(
                    tables["dependabot_alerts"].c.id == alert_id
                )
            ) == "indirect"
            auto_row = connection.execute(
                select(
                    tables["dependabot_alerts"].c.state,
                    tables["dependabot_alerts"].c.dismissed_at,
                    tables["dependabot_alerts"].c.dependency_relationship,
                ).where(tables["dependabot_alerts"].c.id == auto_dismissed_alert_id)
            ).one()
            assert auto_row.state == "dismissed"
            assert auto_row.dismissed_at == now
            assert auto_row.dependency_relationship is None
            connection.execute(
                tables["dependabot_alerts"].delete().where(
                    tables["dependabot_alerts"].c.repository_id == repository_id
                )
            )
            connection.execute(
                tables["security_advisories"].delete().where(
                    tables["security_advisories"].c.id == advisory_id
                )
            )
            connection.execute(
                tables["repositories"].delete().where(
                    tables["repositories"].c.id == repository_id
                )
            )
            connection.execute(
                tables["organizations"].delete().where(
                    tables["organizations"].c.id == organization_id
                )
            )
    finally:
        command.upgrade(config, "head")


def test_representative_references_and_duplicates(postgres_engine: Engine) -> None:
    tables = Base.metadata.tables
    now = datetime.now(UTC)
    organization_a = uuid4()
    organization_b = uuid4()
    repository_id = uuid4()
    advisory_id = uuid4()
    alert_id = uuid4()
    batch_id = uuid4()
    candidate_id = uuid4()
    case_id = uuid4()
    activity_id = uuid4()

    with postgres_engine.begin() as connection:
        connection.execute(
            tables["organizations"].insert(),
            [
                {
                    "id": organization_a,
                    "github_organization_id": 1001,
                    "github_login": "org-a",
                    "display_name": "Organization A",
                },
                {
                    "id": organization_b,
                    "github_organization_id": 1002,
                    "github_login": "org-b",
                    "display_name": "Organization B",
                },
            ],
        )
        connection.execute(
            tables["repositories"].insert(),
            {
                "id": repository_id,
                "organization_id": organization_a,
                "github_repository_id": 2001,
                "full_name": "org-a/example",
                "display_name": "Organization A/example",
                "importance": "high",
                "last_synced_at": now,
            },
        )
        connection.execute(
            tables["security_advisories"].insert(),
            {
                "id": advisory_id,
                "ghsa_id": "GHSA-xxxx-yyyy-zzzz",
                "cve_id": "CVE-2026-12345",
                "summary": "Test advisory",
                "severity": "high",
                "github_updated_at": now,
            },
        )
        connection.execute(
            tables["security_advisories"].insert(),
            {
                "id": uuid4(),
                "ghsa_id": "GHSA-no-cve-example",
                "summary": "Advisory without CVE",
                "severity": "medium",
                "github_updated_at": now,
            },
        )

    alert_values = {
        "id": alert_id,
        "organization_id": organization_a,
        "repository_id": repository_id,
        "advisory_id": advisory_id,
        "github_alert_number": 1,
        "state": "open",
        "package_name": "example-package",
        "ecosystem": "npm",
        "vulnerable_version_range": "< 2.0.0",
        "html_url": "https://github.com/org-a/example/security/dependabot/1",
        "github_created_at": now,
        "github_updated_at": now,
        "last_synced_at": now,
    }
    with postgres_engine.begin() as connection:
        connection.execute(tables["dependabot_alerts"].insert(), alert_values)
        connection.execute(
            tables["gold_batches"].insert(),
            {
                "id": batch_id,
                "source_batch_id": "batch-2026-08-19",
                "as_of": now,
                "source_generated_at": now,
                "policy_version": "v1",
                "schema_version": "v1",
                "candidate_count": 1,
                "synced_at": now,
            },
        )
        connection.execute(
            tables["risk_candidates"].insert(),
            {
                "id": candidate_id,
                "source_candidate_id": "candidate-1",
                "cve_id": "CVE-2026-12345",
                "priority": "high",
                "change_type": "kev_added",
                "reason_summary": "KEV catalog addition",
                "selected_at": now,
            },
        )
        connection.execute(
            tables["candidate_evidence"].insert(),
            {
                "id": uuid4(),
                "source_evidence_id": "evidence-1",
                "candidate_id": candidate_id,
                "signal": "kev",
                "value_type": "boolean",
                "previous_value": "false",
                "current_value": "true",
                "observed_at": now,
                "source": "cisa-kev",
            },
        )
        connection.execute(
            tables["gold_batch_candidates"].insert(),
            {
                "batch_id": batch_id,
                "candidate_id": candidate_id,
                "payload_hash": "a" * 64,
                "received_at": now,
            },
        )
        connection.execute(
            tables["alert_candidate_matches"].insert(),
            {
                "organization_id": organization_a,
                "alert_id": alert_id,
                "candidate_id": candidate_id,
                "matched_at": now,
            },
        )
        connection.execute(
            tables["review_cases"].insert(),
            {
                "id": case_id,
                "organization_id": organization_a,
                "alert_id": alert_id,
                "status": "open",
                "priority": "high",
                "review_reason": "New candidate",
                "opened_at": now,
                "reopened_count": 0,
            },
        )
        connection.execute(
            tables["review_activities"].insert(),
            {
                "id": activity_id,
                "organization_id": organization_a,
                "review_case_id": case_id,
                "candidate_id": candidate_id,
                "activity_type": "case_opened",
                "occurred_at": now,
            },
        )
        connection.execute(
            tables["external_links"].insert(),
            {
                "id": uuid4(),
                "organization_id": organization_a,
                "review_case_id": case_id,
                "created_by_activity_id": activity_id,
                "link_type": "issue",
                "url": "https://github.com/org-a/example/issues/1",
                "github_owner": "org-a",
                "github_repository": "example",
                "github_number": 1,
            },
        )

    with expect_integrity_error(postgres_engine) as connection:
        connection.execute(
            tables["dependabot_alerts"].insert(),
            {**alert_values, "id": uuid4(), "organization_id": organization_b},
        )

    with expect_integrity_error(postgres_engine) as connection:
        connection.execute(
            tables["dependabot_alerts"].insert(),
            {**alert_values, "id": uuid4()},
        )

    with expect_integrity_error(postgres_engine) as connection:
        connection.execute(
            tables["gold_batch_candidates"].insert(),
            {
                "batch_id": batch_id,
                "candidate_id": candidate_id,
                "payload_hash": "a" * 64,
                "received_at": now,
            },
        )

    with expect_integrity_error(postgres_engine) as connection:
        connection.execute(
            tables["alert_candidate_matches"].insert(),
            {
                "organization_id": organization_a,
                "alert_id": alert_id,
                "candidate_id": candidate_id,
                "matched_at": now,
            },
        )

    with expect_integrity_error(postgres_engine) as connection:
        connection.execute(
            tables["review_cases"].insert(),
            {
                "id": uuid4(),
                "organization_id": organization_a,
                "alert_id": alert_id,
                "status": "open",
                "priority": "high",
                "review_reason": "Duplicate case",
                "opened_at": now,
                "reopened_count": 0,
            },
        )

    with expect_integrity_error(postgres_engine) as connection:
        connection.execute(
            tables["review_activities"].insert(),
            {
                "id": uuid4(),
                "organization_id": organization_b,
                "review_case_id": case_id,
                "candidate_id": candidate_id,
                "activity_type": "note_added",
                "occurred_at": now,
            },
        )

    with expect_integrity_error(postgres_engine) as connection:
        connection.execute(
            tables["dependabot_alerts"].insert(),
            {
                **alert_values,
                "id": uuid4(),
                "github_alert_number": 2,
                "state": "dismissed",
            },
        )
