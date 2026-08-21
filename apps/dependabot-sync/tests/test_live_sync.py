from __future__ import annotations

import json
import os

import psycopg
import pytest

from watchback_dependabot_sync.config import REPOSITORIES, Settings
from watchback_dependabot_sync.persistence import normalize_database_url
from watchback_dependabot_sync.service import run_sync


pytestmark = pytest.mark.live


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_DEPENDABOT_SYNC") != "1",
    reason="RUN_LIVE_DEPENDABOT_SYNC=1인 수동 검증에서만 실행합니다.",
)
def test_real_github_snapshot_is_atomic_and_second_run_is_idempotent(
    seeded_database_url,
):
    token = os.environ["GITHUB_TOKEN"]
    settings = Settings(github_token=token, database_url=seeded_database_url)

    first = run_sync(settings)
    with psycopg.connect(normalize_database_url(seeded_database_url)) as connection:
        counts = dict(
            connection.execute(
                """
                SELECT r.full_name, count(a.id)
                  FROM repositories r
                  LEFT JOIN dependabot_alerts a ON a.repository_id = r.id
                 WHERE r.full_name = ANY(%s)
                 GROUP BY r.full_name
                """,
                (list(REPOSITORIES),),
            ).fetchall()
        )
        source_rows_before = connection.execute(
            """
            SELECT a.id, r.full_name, a.github_alert_number, a.advisory_id, a.state,
                   a.package_name, a.ecosystem, a.manifest_path, a.dependency_scope,
                   a.dependency_relationship, a.vulnerable_version_range,
                   a.first_patched_version, a.html_url, a.github_created_at,
                   a.github_updated_at, a.dismissed_at, a.dismissed_reason,
                   a.dismissed_by, a.dismissed_comment, a.fixed_at, a.auto_dismissed_at
              FROM dependabot_alerts a
              JOIN repositories r ON r.id = a.repository_id
             ORDER BY r.full_name, a.github_alert_number
            """
        ).fetchall()

    for full_name in REPOSITORIES:
        assert counts[full_name] == first["repositories"][full_name]["source_count"]

    second = run_sync(settings)
    assert second["changes"]["advisories"]["created"] == 0
    assert second["changes"]["advisories"]["updated"] == 0
    assert second["changes"]["alerts"]["created"] == 0
    assert second["changes"]["alerts"]["updated"] == 0

    with psycopg.connect(normalize_database_url(seeded_database_url)) as connection:
        source_rows_after = connection.execute(
            """
            SELECT a.id, r.full_name, a.github_alert_number, a.advisory_id, a.state,
                   a.package_name, a.ecosystem, a.manifest_path, a.dependency_scope,
                   a.dependency_relationship, a.vulnerable_version_range,
                   a.first_patched_version, a.html_url, a.github_created_at,
                   a.github_updated_at, a.dismissed_at, a.dismissed_reason,
                   a.dismissed_by, a.dismissed_comment, a.fixed_at, a.auto_dismissed_at
              FROM dependabot_alerts a
              JOIN repositories r ON r.id = a.repository_id
             ORDER BY r.full_name, a.github_alert_number
            """
        ).fetchall()
    assert source_rows_after == source_rows_before

    print(
        json.dumps(
            {
                "first": first,
                "second_changes": second["changes"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
