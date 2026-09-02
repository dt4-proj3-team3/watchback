from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect, select, text
from sqlalchemy.exc import IntegrityError, ProgrammingError

from watchback_backend.db.models import Base


EXPECTED_TABLES = {
    "ai_context_documents",
    "alert_candidate_matches",
    "candidate_evidence",
    "dependency_version_snapshots",
    "dependabot_alerts",
    "external_links",
    "gold_batch_candidates",
    "gold_batches",
    "organizations",
    "repositories",
    "remediation_action_targets",
    "remediation_actions",
    "remediation_ai_summaries",
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
    assert review_case.columns["representative_candidate_id"].nullable is False
    assert review_case.columns["representative_batch_id"].nullable is False
    assert any(
        {column.name for column in constraint.columns} == {"alert_id"}
        for constraint in review_case.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    )
    assert any(
        {column.name for column in constraint.columns}
        == {"representative_candidate_id", "representative_batch_id"}
        for constraint in review_case.constraints
        if constraint.__class__.__name__ == "ForeignKeyConstraint"
    )

    match = Base.metadata.tables["alert_candidate_matches"]
    assert {column.name for column in match.primary_key.columns} == {
        "alert_id",
        "candidate_id",
    }

    candidate = Base.metadata.tables["risk_candidates"]
    assert candidate.columns["ghsa_id"].nullable is True
    assert candidate.columns["subject_type"].nullable is False
    assert candidate.columns["subject_id"].nullable is False
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
    assert batch.columns["ds_run_id"].nullable is True

    evidence = Base.metadata.tables["candidate_evidence"]
    assert evidence.columns["batch_id"].nullable is False
    assert evidence.columns["current_value"].nullable is True
    assert evidence.columns["evidence_summary"].nullable is False

    dependency_versions = Base.metadata.tables["dependency_version_snapshots"]
    assert dependency_versions.columns["manifest_path"].nullable is True
    assert dependency_versions.columns["resolved_versions"].nullable is False
    identity_index = next(
        index
        for index in dependency_versions.indexes
        if index.name == "uq_dependency_version_snapshots_identity"
    )
    assert identity_index.unique is True
    assert identity_index.dialect_options["postgresql"]["nulls_not_distinct"] is True

    remediation_action = Base.metadata.tables["remediation_actions"]
    assert remediation_action.columns["watchback_state"].nullable is False
    assert remediation_action.columns["reason_code"].nullable is True
    assert remediation_action.columns["note"].nullable is True
    assert remediation_action.columns["revoked_at"].nullable is True
    assert remediation_action.columns["revoked_by_user_id"].nullable is True
    remediation_target = Base.metadata.tables["remediation_action_targets"]
    assert remediation_target.columns["manifest_path"].nullable is True
    assert remediation_target.columns["revoked_at"].nullable is True
    assert remediation_target.columns["revoked_by_user_id"].nullable is True
    assert {
        "review_case_id",
        "candidate_id",
        "alert_id",
        "repository_id",
    }.issubset(remediation_target.columns.keys())

    remediation_ai_summary = Base.metadata.tables["remediation_ai_summaries"]
    assert remediation_ai_summary.columns["prompt_version"].nullable is False
    assert remediation_ai_summary.columns["source_ids"].nullable is False
    assert remediation_ai_summary.columns["interpretation_note"].nullable is True
    assert any(
        {column.name for column in constraint.columns}
        == {"organization_id", "group_key"}
        for constraint in remediation_ai_summary.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    )

    ai_context_document = Base.metadata.tables["ai_context_documents"]
    assert ai_context_document.columns["content"].nullable is False
    assert ai_context_document.columns["source_url"].nullable is True
    assert any(
        {column.name for column in constraint.columns}
        == {"organization_id", "group_key", "document_type"}
        for constraint in ai_context_document.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    )

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
    assert (
        inspect(postgres_engine).get_table_comment("alert_candidate_matches")["text"]
        == "Dependabot Alert와 Gold 위험 후보의 CVE 매칭 결과"
    )
    command.check(Config(Path(__file__).parents[1] / "alembic.ini"))


def test_dependency_version_snapshot_migration_and_null_manifest_identity(
    postgres_engine: Engine,
) -> None:
    config = Config(Path(__file__).parents[1] / "alembic.ini")
    tables = Base.metadata.tables
    now = datetime.now(UTC)
    organization_id = uuid4()
    repository_id = uuid4()
    first_snapshot_id = uuid4()

    command.downgrade(config, "0008")
    try:
        assert "dependency_version_snapshots" not in inspect(
            postgres_engine
        ).get_table_names()
        command.upgrade(config, "0009")
        assert "dependency_version_snapshots" in inspect(
            postgres_engine
        ).get_table_names()

        with postgres_engine.begin() as connection:
            connection.execute(
                tables["organizations"].insert(),
                {
                    "id": organization_id,
                    "github_organization_id": 9001,
                    "github_login": "dependency-version-migration",
                    "display_name": "Dependency Version Migration",
                },
            )
            connection.execute(
                tables["repositories"].insert(),
                {
                    "id": repository_id,
                    "organization_id": organization_id,
                    "github_repository_id": 9002,
                    "full_name": "dependency-version-migration/example",
                    "display_name": "Dependency Version Migration/example",
                    "importance": "high",
                    "last_synced_at": now,
                },
            )
            connection.execute(
                tables["dependency_version_snapshots"].insert(),
                {
                    "id": first_snapshot_id,
                    "organization_id": organization_id,
                    "repository_id": repository_id,
                    "manifest_path": None,
                    "commit_sha": "a" * 40,
                    "ecosystem": "npm",
                    "package_name": "vite",
                    "resolved_versions": [],
                    "status": "unavailable",
                    "reason": "unsupported_manifest",
                    "observed_at": now,
                },
            )

        with expect_integrity_error(postgres_engine) as connection:
            connection.execute(
                tables["dependency_version_snapshots"].insert(),
                {
                    "id": uuid4(),
                    "organization_id": organization_id,
                    "repository_id": repository_id,
                    "manifest_path": None,
                    "commit_sha": "a" * 40,
                    "ecosystem": "npm",
                    "package_name": "vite",
                    "resolved_versions": [],
                    "status": "unavailable",
                    "reason": "unsupported_manifest",
                    "observed_at": now,
                },
            )

        command.downgrade(config, "0008")
        assert "dependency_version_snapshots" not in inspect(
            postgres_engine
        ).get_table_names()
    finally:
        command.upgrade(config, "head")


def test_remediation_action_migration_upgrade_and_downgrade(
    postgres_engine: Engine,
) -> None:
    config = Config(Path(__file__).parents[1] / "alembic.ini")

    command.downgrade(config, "0009")
    try:
        table_names = set(inspect(postgres_engine).get_table_names())
        assert "remediation_actions" not in table_names
        assert "remediation_action_targets" not in table_names

        command.upgrade(config, "0010")
        table_names = set(inspect(postgres_engine).get_table_names())
        assert "remediation_actions" in table_names
        assert "remediation_action_targets" in table_names

        command.downgrade(config, "0009")
        table_names = set(inspect(postgres_engine).get_table_names())
        assert "remediation_actions" not in table_names
        assert "remediation_action_targets" not in table_names
    finally:
        command.upgrade(config, "head")


def test_remediation_ai_summary_migration_upgrade_and_downgrade(
    postgres_engine: Engine,
) -> None:
    config = Config(Path(__file__).parents[1] / "alembic.ini")

    command.downgrade(config, "0010")
    try:
        assert "remediation_ai_summaries" not in inspect(
            postgres_engine
        ).get_table_names()
        command.upgrade(config, "0011")
        assert "remediation_ai_summaries" in inspect(
            postgres_engine
        ).get_table_names()
        command.downgrade(config, "0010")
        assert "remediation_ai_summaries" not in inspect(
            postgres_engine
        ).get_table_names()
    finally:
        command.upgrade(config, "head")


def test_ai_summary_interpretation_note_migration_upgrade_and_downgrade(
    postgres_engine: Engine,
) -> None:
    config = Config(Path(__file__).parents[1] / "alembic.ini")

    command.downgrade(config, "0013")
    try:
        columns = {
            column["name"]
            for column in inspect(postgres_engine).get_columns(
                "remediation_ai_summaries"
            )
        }
        assert "interpretation_note" not in columns
        command.upgrade(config, "0014")
        columns = {
            column["name"]
            for column in inspect(postgres_engine).get_columns(
                "remediation_ai_summaries"
            )
        }
        assert "interpretation_note" in columns
        command.downgrade(config, "0013")
        columns = {
            column["name"]
            for column in inspect(postgres_engine).get_columns(
                "remediation_ai_summaries"
            )
        }
        assert "interpretation_note" not in columns
    finally:
        command.upgrade(config, "head")


def test_ai_context_document_migration_upgrade_and_downgrade(
    postgres_engine: Engine,
) -> None:
    config = Config(Path(__file__).parents[1] / "alembic.ini")

    command.downgrade(config, "0016")
    try:
        assert "ai_context_documents" not in inspect(
            postgres_engine
        ).get_table_names()
        command.upgrade(config, "0017")
        assert "ai_context_documents" in inspect(
            postgres_engine
        ).get_table_names()
        command.downgrade(config, "0016")
        assert "ai_context_documents" not in inspect(
            postgres_engine
        ).get_table_names()
    finally:
        command.upgrade(config, "head")


def test_risk_acceptance_lifecycle_migration_upgrade_and_downgrade(
    postgres_engine: Engine,
) -> None:
    config = Config(Path(__file__).parents[1] / "alembic.ini")

    command.downgrade(config, "0011")
    try:
        columns = {
            column["name"]
            for column in inspect(postgres_engine).get_columns(
                "remediation_actions"
            )
        }
        assert "reason_code" not in columns
        command.upgrade(config, "0012")
        columns = {
            column["name"]
            for column in inspect(postgres_engine).get_columns(
                "remediation_actions"
            )
        }
        assert {
            "reason_code",
            "revoked_at",
            "revoked_by_user_id",
            "revocation_note",
        }.issubset(columns)
        command.downgrade(config, "0011")
        columns = {
            column["name"]
            for column in inspect(postgres_engine).get_columns(
                "remediation_actions"
            )
        }
        assert "reason_code" not in columns
    finally:
        command.upgrade(config, "head")


def test_remediation_target_lifecycle_migration_upgrade_and_downgrade(
    postgres_engine: Engine,
) -> None:
    config = Config(Path(__file__).parents[1] / "alembic.ini")

    command.downgrade(config, "0012")
    try:
        columns = {
            column["name"]
            for column in inspect(postgres_engine).get_columns(
                "remediation_action_targets"
            )
        }
        assert "revoked_at" not in columns
        command.upgrade(config, "0013")
        columns = {
            column["name"]
            for column in inspect(postgres_engine).get_columns(
                "remediation_action_targets"
            )
        }
        assert {
            "revoked_at",
            "revoked_by_user_id",
            "revocation_note",
        }.issubset(columns)
    finally:
        command.upgrade(config, "head")


def test_gold_contract_migration_rejects_existing_gold_rows(
    postgres_engine: Engine,
) -> None:
    config = Config(Path(__file__).parents[1] / "alembic.ini")
    command.downgrade(config, "0003")
    try:
        with postgres_engine.begin() as connection:
            connection.execute(
                Base.metadata.tables["gold_batches"].insert(),
                {
                    "id": uuid4(),
                    "source_batch_id": "migration-precondition",
                    "as_of": datetime.now(UTC),
                    "source_generated_at": datetime.now(UTC),
                    "policy_version": "ver.1",
                    "schema_version": "1.0",
                    "candidate_count": 0,
                    "synced_at": datetime.now(UTC),
                },
            )
        with pytest.raises(ProgrammingError, match="Gold 계약 upgrade"):
            command.upgrade(config, "head")
    finally:
        with postgres_engine.begin() as connection:
            connection.execute(Base.metadata.tables["gold_batches"].delete())
        command.upgrade(config, "head")


def test_case_representative_migration_rejects_existing_cases(
    postgres_engine: Engine,
) -> None:
    config = Config(Path(__file__).parents[1] / "alembic.ini")
    case_id = uuid4()
    command.downgrade(config, "0005")
    try:
        with postgres_engine.begin() as connection:
            connection.execute(text("SET session_replication_role = replica"))
            connection.execute(
                text(
                    """
                    INSERT INTO review_cases (
                        id, organization_id, alert_id, status, priority,
                        review_reason, opened_at, reopened_count
                    ) VALUES (
                        :id, :organization_id, :alert_id, 'open', 'high',
                        'migration precondition', :opened_at, 0
                    )
                    """
                ),
                {
                    "id": case_id,
                    "organization_id": uuid4(),
                    "alert_id": uuid4(),
                    "opened_at": datetime.now(UTC),
                },
            )
            connection.execute(text("SET session_replication_role = origin"))
        with pytest.raises(ProgrammingError, match="대표 Candidate와 Batch"):
            command.upgrade(config, "head")
    finally:
        with postgres_engine.begin() as connection:
            connection.execute(text("SET session_replication_role = replica"))
            connection.execute(
                text("DELETE FROM review_cases WHERE id = :id"), {"id": case_id}
            )
            connection.execute(text("SET session_replication_role = origin"))
        command.upgrade(config, "head")


def test_cve_matching_migration_rejects_ghsa_only_candidate(
    postgres_engine: Engine,
) -> None:
    config = Config(Path(__file__).parents[1] / "alembic.ini")
    candidate_id = uuid4()
    command.downgrade(config, "0006")
    try:
        with postgres_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO risk_candidates (
                        id, source_candidate_id, subject_type, subject_id,
                        ghsa_id, cve_id, priority, change_type,
                        reason_summary, selected_at
                    ) VALUES (
                        :id, 'ghsa-only-migration-test', 'GHSA',
                        'GHSA-AAAA-BBBB-CCCC', 'GHSA-AAAA-BBBB-CCCC', NULL,
                        'P3', 'test', 'migration precondition', :selected_at
                    )
                    """
                ),
                {"id": candidate_id, "selected_at": datetime.now(UTC)},
            )
        with pytest.raises(ProgrammingError, match="CVE 기준으로 변환"):
            command.upgrade(config, "head")
    finally:
        with postgres_engine.begin() as connection:
            connection.execute(
                text("DELETE FROM risk_candidates WHERE id = :id"),
                {"id": candidate_id},
            )
        command.upgrade(config, "head")


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
                tables["repositories"]
                .delete()
                .where(tables["repositories"].c.id == repository_id)
            )
            connection.execute(
                tables["organizations"]
                .delete()
                .where(tables["organizations"].c.id == organization_id)
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
            assert (
                connection.scalar(
                    select(tables["security_advisories"].c.severity).where(
                        tables["security_advisories"].c.id == advisory_id
                    )
                )
                == "medium"
            )
            assert (
                connection.scalar(
                    select(tables["dependabot_alerts"].c.dependency_relationship).where(
                        tables["dependabot_alerts"].c.id == alert_id
                    )
                )
                == "transitive"
            )
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
            assert (
                connection.scalar(
                    select(tables["security_advisories"].c.severity).where(
                        tables["security_advisories"].c.id == advisory_id
                    )
                )
                == "moderate"
            )
            assert (
                connection.scalar(
                    select(tables["dependabot_alerts"].c.dependency_relationship).where(
                        tables["dependabot_alerts"].c.id == alert_id
                    )
                )
                == "indirect"
            )
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
                tables["dependabot_alerts"]
                .delete()
                .where(tables["dependabot_alerts"].c.repository_id == repository_id)
            )
            connection.execute(
                tables["security_advisories"]
                .delete()
                .where(tables["security_advisories"].c.id == advisory_id)
            )
            connection.execute(
                tables["repositories"]
                .delete()
                .where(tables["repositories"].c.id == repository_id)
            )
            connection.execute(
                tables["organizations"]
                .delete()
                .where(tables["organizations"].c.id == organization_id)
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
                "subject_type": "CVE",
                "subject_id": "CVE-2026-12345",
                "ghsa_id": "GHSA-example-candidate",
                "cve_id": "CVE-2026-12345",
                "priority": "P1",
                "change_type": "kev_added",
                "reason_summary": "KEV catalog addition",
                "selected_at": now,
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
            tables["candidate_evidence"].insert(),
            {
                "id": uuid4(),
                "source_evidence_id": "evidence-1",
                "batch_id": batch_id,
                "candidate_id": candidate_id,
                "signal": "kev",
                "value_type": "boolean",
                "previous_value": "false",
                "current_value": "true",
                "observed_at": now,
                "source": "cisa-kev",
                "evidence_summary": "CISA KEV 등재",
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
                "representative_candidate_id": candidate_id,
                "representative_batch_id": batch_id,
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
                "representative_candidate_id": candidate_id,
                "representative_batch_id": batch_id,
                "status": "open",
                "priority": "high",
                "review_reason": "Duplicate case",
                "opened_at": now,
                "reopened_count": 0,
            },
        )

    with expect_integrity_error(postgres_engine) as connection:
        connection.execute(
            tables["review_cases"]
            .update()
            .where(tables["review_cases"].c.id == case_id)
            .values(representative_batch_id=uuid4())
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
