from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import psycopg
import pytest

from watchback_dependabot_sync.config import REPOSITORIES
from watchback_dependabot_sync.errors import PersistenceError
from watchback_dependabot_sync.models import (
    AlertPayload,
    CvssSeveritiesPayload,
    RepositoryPayload,
)
from watchback_dependabot_sync.persistence import (
    LOCK_KEY,
    _first_patched_version,
    normalize_database_url,
    persist_snapshot,
    verify_reference_data,
)
from watchback_dependabot_sync.service import collect_advisories
from watchback_dependabot_sync.versions import DependencyVersionResult


def repository_payloads():
    return {
        name: RepositoryPayload(
            id=identifier,
            full_name=name,
            default_branch="main",
            updated_at="2026-08-21T00:00:00Z",
        )
        for name, identifier in REPOSITORIES.items()
    }


def test_litellm_advisory_patch_version_override() -> None:
    alert = SimpleNamespace(
        security_advisory=SimpleNamespace(cve_id="CVE-2026-40217"),
        security_vulnerability=SimpleNamespace(
            first_patched_version=SimpleNamespace(identifier="1.83.10")
        ),
    )

    assert _first_patched_version(alert) == "1.83.11"


def source_snapshot(raw_alerts):
    parsed = [AlertPayload.model_validate(item) for item in raw_alerts]
    names = list(REPOSITORIES)
    return {
        names[0]: parsed[:4],
        names[1]: parsed[4:],
        names[2]: [],
        names[3]: [],
    }


@pytest.mark.integration
def test_upsert_deduplicates_advisory_preserves_manifest_and_is_idempotent(
    seeded_database_url, raw_alerts
):
    alerts = source_snapshot(raw_alerts)
    advisories = collect_advisories(alerts)
    now = datetime.now(UTC)
    first = persist_snapshot(
        seeded_database_url, repository_payloads(), alerts, advisories, now
    )
    assert first["advisories"]["created"] == 4
    assert first["alerts"]["created"] == 5

    with psycopg.connect(normalize_database_url(seeded_database_url)) as connection:
        advisory_count = connection.execute(
            "SELECT count(*) FROM security_advisories"
        ).fetchone()[0]
        alert_count = connection.execute("SELECT count(*) FROM dependabot_alerts").fetchone()[0]
        manifests = connection.execute(
            "SELECT manifest_path FROM dependabot_alerts "
            "WHERE package_name = 'vite' ORDER BY manifest_path"
        ).fetchall()
        ids_before = connection.execute(
            "SELECT github_alert_number, id FROM dependabot_alerts ORDER BY github_alert_number"
        ).fetchall()
    assert advisory_count == 4
    assert alert_count == 5
    assert [row[0] for row in manifests] == ["examples/package-lock.json", "package-lock.json"]

    second = persist_snapshot(
        seeded_database_url,
        repository_payloads(),
        alerts,
        advisories,
        now + timedelta(minutes=1),
    )
    assert second["advisories"]["unchanged"] == 4
    assert second["alerts"]["unchanged"] == 5
    with psycopg.connect(normalize_database_url(seeded_database_url)) as connection:
        ids_after = connection.execute(
            "SELECT github_alert_number, id FROM dependabot_alerts ORDER BY github_alert_number"
        ).fetchall()
    assert ids_after == ids_before


@pytest.mark.integration
def test_equal_timestamp_repairs_cvss_projection_and_then_is_idempotent(
    seeded_database_url, raw_alerts
):
    alerts = source_snapshot(raw_alerts)
    now = datetime.now(UTC)
    persist_snapshot(
        seeded_database_url,
        repository_payloads(),
        alerts,
        collect_advisories(alerts),
        now,
    )

    target_ghsa = alerts[list(REPOSITORIES)[0]][0].security_advisory.ghsa_id
    for repository_alerts in alerts.values():
        for alert in repository_alerts:
            advisory = alert.security_advisory
            if advisory.ghsa_id != target_ghsa:
                continue
            advisory.cvss.score = Decimal("0")
            advisory.cvss.vector_string = None
            advisory.cvss_severities = CvssSeveritiesPayload.model_validate({
                "cvss_v4": {
                    "vector_string": "CVSS:4.0/AV:N/AC:L/AT:P/PR:N/UI:N/VC:H",
                    "score": 8.2,
                }
            })

    repaired = persist_snapshot(
        seeded_database_url,
        repository_payloads(),
        alerts,
        collect_advisories(alerts),
        now + timedelta(minutes=1),
    )
    assert repaired["advisories"]["updated"] == 1

    with psycopg.connect(normalize_database_url(seeded_database_url)) as connection:
        score = connection.execute(
            "SELECT cvss_score FROM security_advisories WHERE ghsa_id = %s",
            (target_ghsa,),
        ).fetchone()[0]
    assert score == Decimal("8.20")

    repeated = persist_snapshot(
        seeded_database_url,
        repository_payloads(),
        alerts,
        collect_advisories(alerts),
        now + timedelta(minutes=2),
    )
    assert repeated["advisories"]["unchanged"] == 4


@pytest.mark.integration
def test_stale_payload_and_missing_alert_do_not_overwrite_or_delete(
    seeded_database_url, raw_alerts
):
    alerts = source_snapshot(raw_alerts)
    now = datetime.now(UTC)
    persist_snapshot(
        seeded_database_url,
        repository_payloads(),
        alerts,
        collect_advisories(alerts),
        now,
    )
    first_repo = list(REPOSITORIES)[0]
    stale = alerts[first_repo][0].model_copy(deep=True)
    stale.updated_at -= timedelta(days=1)
    stale.state = "dismissed"
    stale.dismissed_at = stale.updated_at
    reduced = {**alerts, first_repo: [stale]}
    result = persist_snapshot(
        seeded_database_url,
        repository_payloads(),
        reduced,
        collect_advisories(reduced),
        now + timedelta(minutes=1),
    )
    assert result["alerts"]["stale"] == 1
    with psycopg.connect(normalize_database_url(seeded_database_url)) as connection:
        state = connection.execute(
            "SELECT state FROM dependabot_alerts WHERE github_alert_number = 1"
        ).fetchone()[0]
        count = connection.execute("SELECT count(*) FROM dependabot_alerts").fetchone()[0]
    assert state == "open"
    assert count == 5

    newer = stale.model_copy(deep=True)
    newer.updated_at += timedelta(days=2)
    result = persist_snapshot(
        seeded_database_url,
        repository_payloads(),
        {**alerts, first_repo: [newer]},
        collect_advisories({**alerts, first_repo: [newer]}),
        now + timedelta(minutes=2),
    )
    assert result["alerts"]["updated"] == 1
    with psycopg.connect(normalize_database_url(seeded_database_url)) as connection:
        assert connection.execute(
            "SELECT state FROM dependabot_alerts WHERE github_alert_number = 1"
        ).fetchone()[0] == "dismissed"


@pytest.mark.integration
def test_invalid_write_rolls_back_all_repositories(seeded_database_url, raw_alerts):
    alerts = source_snapshot(raw_alerts)
    second_repo = list(REPOSITORIES)[1]
    alerts[second_repo][0].dependency.package.name = "x" * 300
    with pytest.raises(PersistenceError, match="원자 반영"):
        persist_snapshot(
            seeded_database_url,
            repository_payloads(),
            alerts,
            collect_advisories(alerts),
            datetime.now(UTC),
        )
    with psycopg.connect(normalize_database_url(seeded_database_url)) as connection:
        assert connection.execute("SELECT count(*) FROM security_advisories").fetchone()[0] == 0
        assert connection.execute("SELECT count(*) FROM dependabot_alerts").fetchone()[0] == 0


@pytest.mark.integration
def test_reference_mismatch_and_concurrent_lock_are_rejected(seeded_database_url, raw_alerts):
    references = verify_reference_data(seeded_database_url)
    assert set(references) == set(REPOSITORIES)
    alerts = source_snapshot(raw_alerts)
    with psycopg.connect(normalize_database_url(seeded_database_url)) as lock_connection:
        lock_connection.execute("SELECT pg_advisory_xact_lock(%s)", (LOCK_KEY,))
        with pytest.raises(PersistenceError, match="실행 중"):
            persist_snapshot(
                seeded_database_url,
                repository_payloads(),
                alerts,
                collect_advisories(alerts),
                datetime.now(UTC),
            )

    with psycopg.connect(normalize_database_url(seeded_database_url)) as connection:
        full_name = list(REPOSITORIES)[0]
        connection.execute(
            "UPDATE repositories SET github_repository_id = github_repository_id + 1 "
            "WHERE full_name = %s",
            (full_name,),
        )
    with pytest.raises(PersistenceError, match="식별자"):
        verify_reference_data(seeded_database_url)


@pytest.mark.integration
def test_dependency_versions_are_persisted_idempotently(
    seeded_database_url, raw_alerts
):
    alerts = source_snapshot(raw_alerts)
    repositories = repository_payloads()
    full_name = list(REPOSITORIES)[0]
    observed_at = datetime.now(UTC)
    resolved = DependencyVersionResult(
        repository=full_name,
        manifest_path="package-lock.json",
        commit_sha="a" * 40,
        ecosystem="npm",
        package_name="vite",
        resolved_versions=("5.4.0", "6.4.1"),
        status="multiple",
        reason=None,
        source_path="package-lock.json",
        source_blob_sha="b" * 40,
        observed_at=observed_at,
    )
    unavailable = DependencyVersionResult(
        repository=full_name,
        manifest_path=None,
        commit_sha="a" * 40,
        ecosystem="npm",
        package_name="unknown-package",
        resolved_versions=(),
        status="unavailable",
        reason="unsupported_manifest",
        source_path=None,
        source_blob_sha=None,
        observed_at=observed_at,
    )
    versions = {full_name: [resolved, unavailable]}

    first = persist_snapshot(
        seeded_database_url,
        repositories,
        alerts,
        collect_advisories(alerts),
        observed_at,
        versions,
    )
    assert first["dependency_versions"]["created"] == 2

    with psycopg.connect(normalize_database_url(seeded_database_url)) as connection:
        before = connection.execute(
            """
            SELECT id, manifest_path, resolved_versions, status, reason, observed_at
              FROM dependency_version_snapshots
             ORDER BY package_name
            """
        ).fetchall()
    assert len(before) == 2
    assert before[1][2] == ["5.4.0", "6.4.1"]

    repeated_at = observed_at + timedelta(minutes=1)
    repeated = persist_snapshot(
        seeded_database_url,
        repositories,
        alerts,
        collect_advisories(alerts),
        repeated_at,
        {
            full_name: [
                replace(resolved, observed_at=repeated_at),
                replace(unavailable, observed_at=repeated_at),
            ]
        },
    )
    assert repeated["dependency_versions"]["unchanged"] == 2

    with psycopg.connect(normalize_database_url(seeded_database_url)) as connection:
        after = connection.execute(
            """
            SELECT id, manifest_path, resolved_versions, status, reason, observed_at
              FROM dependency_version_snapshots
             ORDER BY package_name
            """
        ).fetchall()
    assert after == before
