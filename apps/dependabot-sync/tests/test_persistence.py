from __future__ import annotations

from datetime import UTC, datetime, timedelta

import psycopg
import pytest

from watchback_dependabot_sync.config import REPOSITORIES
from watchback_dependabot_sync.errors import PersistenceError
from watchback_dependabot_sync.models import AlertPayload, RepositoryPayload
from watchback_dependabot_sync.persistence import (
    LOCK_KEY,
    normalize_database_url,
    persist_snapshot,
    verify_reference_data,
)
from watchback_dependabot_sync.service import collect_advisories


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


def source_snapshot(raw_alerts):
    parsed = [AlertPayload.model_validate(item) for item in raw_alerts]
    names = list(REPOSITORIES)
    return {names[0]: parsed[:4], names[1]: parsed[4:]}


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
def test_invalid_write_rolls_back_both_repositories(seeded_database_url, raw_alerts):
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
