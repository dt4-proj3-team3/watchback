from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

import psycopg
from psycopg.rows import dict_row

from .config import ORGANIZATION_GITHUB_ID, ORGANIZATION_LOGIN, REPOSITORIES
from .errors import PersistenceError
from .models import AdvisoryPayload, AlertPayload, RepositoryPayload


LOCK_KEY = 890089


def normalize_database_url(url: str) -> str:
    return url.replace("postgresql+psycopg://", "postgresql://", 1).replace(
        "postgresql+psycopg2://", "postgresql://", 1
    )


def advisory_uuid(ghsa_id: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"watchback:security-advisory:{ghsa_id}")


def alert_uuid(repository_github_id: int, alert_number: int) -> UUID:
    return uuid5(
        NAMESPACE_URL,
        f"watchback:dependabot-alert:{repository_github_id}:{alert_number}",
    )


@dataclass(frozen=True)
class RepositoryReference:
    id: UUID
    organization_id: UUID
    github_repository_id: int
    full_name: str


@dataclass
class ChangeCounts:
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    stale: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "created": self.created,
            "updated": self.updated,
            "unchanged": self.unchanged,
            "stale": self.stale,
        }


def _load_references(cursor: psycopg.Cursor[Any]) -> dict[str, RepositoryReference]:
    cursor.execute(
        """
        SELECT o.id AS organization_id, o.github_organization_id, o.github_login,
               r.id, r.github_repository_id, r.full_name
          FROM organizations o
          JOIN repositories r ON r.organization_id = o.id
         WHERE o.github_login = %s AND r.full_name = ANY(%s)
        """,
        (ORGANIZATION_LOGIN, list(REPOSITORIES)),
    )
    rows = cursor.fetchall()
    if len(rows) != len(REPOSITORIES):
        raise PersistenceError(
            "reference_data_missing",
            "노바링크 조직 또는 대상 저장소 기준 데이터가 없습니다.",
        )
    references: dict[str, RepositoryReference] = {}
    for row in rows:
        expected_repository_id = REPOSITORIES.get(row["full_name"])
        if (
            row["github_organization_id"] != ORGANIZATION_GITHUB_ID
            or row["github_login"] != ORGANIZATION_LOGIN
            or row["github_repository_id"] != expected_repository_id
        ):
            raise PersistenceError(
                "reference_data_mismatch",
                "조직 또는 저장소 외부 식별자가 기준 데이터와 다릅니다.",
                context={"repository": row["full_name"]},
            )
        references[row["full_name"]] = RepositoryReference(
            id=row["id"],
            organization_id=row["organization_id"],
            github_repository_id=row["github_repository_id"],
            full_name=row["full_name"],
        )
    return references


def verify_reference_data(database_url: str) -> dict[str, RepositoryReference]:
    try:
        with psycopg.connect(
            normalize_database_url(database_url), row_factory=dict_row
        ) as connection:
            with connection.cursor() as cursor:
                return _load_references(cursor)
    except PersistenceError:
        raise
    except psycopg.Error as exc:
        raise PersistenceError(
            "database_preflight_failed", "DB 사전 확인에 실패했습니다."
        ) from exc


def _upsert_advisory(
    cursor: psycopg.Cursor[Any], advisory: AdvisoryPayload
) -> tuple[UUID, str]:
    cursor.execute(
        """
        SELECT id, cve_id, summary, description, severity, cvss_score,
               github_published_at, github_updated_at, github_withdrawn_at
          FROM security_advisories
         WHERE ghsa_id = %s
        """,
        (advisory.ghsa_id,),
    )
    existing = cursor.fetchone()
    values = (
        advisory.cve_id,
        advisory.summary,
        advisory.description,
        advisory.severity,
        advisory.effective_cvss_score,
        advisory.published_at,
        advisory.updated_at,
        advisory.withdrawn_at,
    )
    if existing is None:
        identifier = advisory_uuid(advisory.ghsa_id)
        cursor.execute(
            """
            INSERT INTO security_advisories
                (id, ghsa_id, cve_id, summary, description, severity, cvss_score,
                 github_published_at, github_updated_at, github_withdrawn_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (identifier, advisory.ghsa_id, *values),
        )
        return identifier, "created"
    stored_values = (
        existing["cve_id"],
        existing["summary"],
        existing["description"],
        existing["severity"],
        existing["cvss_score"],
        existing["github_published_at"],
        existing["github_updated_at"],
        existing["github_withdrawn_at"],
    )
    should_update = advisory.updated_at > existing["github_updated_at"] or (
        advisory.updated_at == existing["github_updated_at"]
        and values != stored_values
    )
    if should_update:
        cursor.execute(
            """
            UPDATE security_advisories
               SET cve_id = %s, summary = %s, description = %s, severity = %s,
                   cvss_score = %s, github_published_at = %s, github_updated_at = %s,
                   github_withdrawn_at = %s, updated_at = now()
             WHERE id = %s
            """,
            (*values, existing["id"]),
        )
        return existing["id"], "updated"
    action = (
        "stale"
        if advisory.updated_at < existing["github_updated_at"]
        else "unchanged"
    )
    return existing["id"], action


def _alert_values(
    alert: AlertPayload, advisory_id: UUID, reference: RepositoryReference
) -> tuple[Any, ...]:
    vulnerability = alert.security_vulnerability
    return (
        advisory_id,
        alert.state,
        alert.dependency.package.name,
        alert.dependency.package.ecosystem,
        alert.dependency.manifest_path,
        alert.dependency.scope,
        alert.dependency.relationship,
        vulnerability.vulnerable_version_range,
        vulnerability.first_patched_version.identifier
        if vulnerability.first_patched_version
        else None,
        str(alert.html_url),
        alert.created_at,
        alert.updated_at,
        alert.dismissed_at,
        alert.dismissed_reason,
        alert.dismissed_by.login if alert.dismissed_by else None,
        alert.dismissed_comment,
        alert.fixed_at,
        alert.auto_dismissed_at,
        reference.organization_id,
        reference.id,
    )


def _upsert_alert(
    cursor: psycopg.Cursor[Any],
    alert: AlertPayload,
    advisory_id: UUID,
    reference: RepositoryReference,
    synced_at: datetime,
) -> str:
    cursor.execute(
        """
        SELECT id, github_updated_at FROM dependabot_alerts
         WHERE repository_id = %s AND github_alert_number = %s
        """,
        (reference.id, alert.number),
    )
    existing = cursor.fetchone()
    values = _alert_values(alert, advisory_id, reference)
    if existing is None:
        cursor.execute(
            """
            INSERT INTO dependabot_alerts
                (id, advisory_id, state, package_name, ecosystem, manifest_path,
                 dependency_scope, dependency_relationship, vulnerable_version_range,
                 first_patched_version, html_url, github_created_at, github_updated_at,
                 dismissed_at, dismissed_reason, dismissed_by, dismissed_comment,
                 fixed_at, auto_dismissed_at, organization_id, repository_id,
                 github_alert_number, last_synced_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                alert_uuid(reference.github_repository_id, alert.number),
                *values,
                alert.number,
                synced_at,
            ),
        )
        return "created"
    action = "stale" if alert.updated_at < existing["github_updated_at"] else "unchanged"
    if alert.updated_at > existing["github_updated_at"]:
        cursor.execute(
            """
            UPDATE dependabot_alerts
               SET advisory_id = %s, state = %s, package_name = %s, ecosystem = %s,
                   manifest_path = %s, dependency_scope = %s, dependency_relationship = %s,
                   vulnerable_version_range = %s, first_patched_version = %s,
                   html_url = %s, github_created_at = %s, github_updated_at = %s,
                   dismissed_at = %s, dismissed_reason = %s, dismissed_by = %s,
                   dismissed_comment = %s, fixed_at = %s, auto_dismissed_at = %s,
                   organization_id = %s, repository_id = %s,
                   last_synced_at = %s, updated_at = now()
             WHERE id = %s
            """,
            (*values, synced_at, existing["id"]),
        )
        return "updated"
    cursor.execute(
        "UPDATE dependabot_alerts SET last_synced_at = %s, updated_at = now() WHERE id = %s",
        (synced_at, existing["id"]),
    )
    return action


def _increment(counts: ChangeCounts, action: str) -> None:
    setattr(counts, action, getattr(counts, action) + 1)


def persist_snapshot(
    database_url: str,
    repositories: dict[str, RepositoryPayload],
    alerts: dict[str, list[AlertPayload]],
    advisories: dict[str, AdvisoryPayload],
    synced_at: datetime,
) -> dict[str, dict[str, int]]:
    advisory_counts = ChangeCounts()
    alert_counts = ChangeCounts()
    try:
        with psycopg.connect(
            normalize_database_url(database_url), row_factory=dict_row
        ) as connection:
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute("SELECT pg_try_advisory_xact_lock(%s)", (LOCK_KEY,))
                if not cursor.fetchone()["pg_try_advisory_xact_lock"]:
                    raise PersistenceError(
                        "sync_already_running",
                        "다른 Dependabot 동기화가 실행 중입니다.",
                    )
                references = _load_references(cursor)

                advisory_ids: dict[str, UUID] = {}
                for ghsa_id in sorted(advisories):
                    identifier, action = _upsert_advisory(cursor, advisories[ghsa_id])
                    advisory_ids[ghsa_id] = identifier
                    _increment(advisory_counts, action)

                for full_name in sorted(repositories):
                    repository = repositories[full_name]
                    reference = references[full_name]
                    cursor.execute(
                        "SELECT github_updated_at FROM repositories WHERE id = %s",
                        (reference.id,),
                    )
                    current_updated_at = cursor.fetchone()["github_updated_at"]
                    if current_updated_at is None or repository.updated_at > current_updated_at:
                        cursor.execute(
                            """
                            UPDATE repositories
                               SET full_name = %s, default_branch = %s, github_updated_at = %s,
                                   last_synced_at = %s, updated_at = now()
                             WHERE id = %s
                            """,
                            (
                                repository.full_name,
                                repository.default_branch,
                                repository.updated_at,
                                synced_at,
                                reference.id,
                            ),
                        )
                    else:
                        cursor.execute(
                            "UPDATE repositories SET last_synced_at = %s, "
                            "updated_at = now() WHERE id = %s",
                            (synced_at, reference.id),
                        )

                    for alert in sorted(alerts[full_name], key=lambda item: item.number):
                        action = _upsert_alert(
                            cursor,
                            alert,
                            advisory_ids[alert.security_advisory.ghsa_id],
                            reference,
                            synced_at,
                        )
                        _increment(alert_counts, action)
        return {"advisories": advisory_counts.as_dict(), "alerts": alert_counts.as_dict()}
    except PersistenceError:
        raise
    except psycopg.Error as exc:
        raise PersistenceError(
            "database_write_failed", "DB 원자 반영에 실패했습니다."
        ) from exc
