from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from .config import GITHUB_API_VERSION, REPOSITORIES, Settings
from .errors import ContractError, SyncError
from .github import GitHubClient
from .models import AdvisoryPayload, AlertPayload, RepositoryPayload
from .persistence import persist_snapshot, verify_reference_data


def _canonical_advisory(advisory: AdvisoryPayload) -> str:
    payload = advisory.model_dump(mode="json")
    payload["identifiers"] = sorted(
        payload["identifiers"], key=lambda item: (item["type"], item["value"])
    )
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def collect_advisories(
    alerts_by_repository: dict[str, list[AlertPayload]],
) -> dict[str, AdvisoryPayload]:
    advisories: dict[str, AdvisoryPayload] = {}
    canonical: dict[str, str] = {}
    for alerts in alerts_by_repository.values():
        for alert in alerts:
            advisory = alert.security_advisory
            existing = advisories.get(advisory.ghsa_id)
            payload = _canonical_advisory(advisory)
            if existing is None or advisory.updated_at > existing.updated_at:
                advisories[advisory.ghsa_id] = advisory
                canonical[advisory.ghsa_id] = payload
            elif (
                advisory.updated_at == existing.updated_at
                and canonical[advisory.ghsa_id] != payload
            ):
                raise ContractError(
                    "conflicting_advisory_payload",
                    "동일 시각의 GHSA payload가 서로 다릅니다.",
                    context={"ghsa_id": advisory.ghsa_id},
                )
    return advisories


def repository_digest(alerts: list[AlertPayload]) -> str:
    canonical = json.dumps(
        [item.model_dump(mode="json") for item in sorted(alerts, key=lambda item: item.number)],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def repository_summary(alerts: list[AlertPayload], pages: int) -> dict[str, Any]:
    return {
        "pages": pages,
        "source_count": len(alerts),
        "states": dict(sorted(Counter(item.state for item in alerts).items())),
        "severities": dict(
            sorted(Counter(item.security_advisory.severity for item in alerts).items())
        ),
        "missing_cve_count": sum(item.security_advisory.cve_id is None for item in alerts),
        "unique_advisory_count": len({item.security_advisory.ghsa_id for item in alerts}),
        "excluded_count": 0,
        "excluded_reasons": {},
        "sha256": repository_digest(alerts),
    }


def run_sync(settings: Settings, *, client: GitHubClient | None = None) -> dict[str, Any]:
    try:
        verify_reference_data(settings.database_url)
    except SyncError as exc:
        exc.context = {"stage": "preflight", **exc.context}
        raise
    owns_client = client is None
    github = client or GitHubClient(
        settings.github_token,
        api_url=settings.github_api_url,
    )
    repositories: dict[str, RepositoryPayload] = {}
    alerts_by_repository: dict[str, list[AlertPayload]] = {}
    summaries: dict[str, dict[str, Any]] = {}
    try:
        try:
            for full_name, expected_id in REPOSITORIES.items():
                repository = github.get_repository(full_name)
                if repository.id != expected_id or repository.full_name != full_name:
                    raise ContractError(
                        "repository_identity_mismatch",
                        "GitHub 저장소 ID 또는 full_name이 기준 데이터와 다릅니다.",
                        context={"repository": full_name},
                    )
                alerts, pages = github.get_alerts(full_name)
                repositories[full_name] = repository
                alerts_by_repository[full_name] = alerts
                summaries[full_name] = repository_summary(alerts, pages)
        except SyncError as exc:
            stage = "validation" if isinstance(exc, ContractError) else "fetch"
            exc.context = {"stage": stage, **exc.context}
            raise
    finally:
        if owns_client:
            github.close()

    try:
        advisories = collect_advisories(alerts_by_repository)
    except SyncError as exc:
        exc.context = {"stage": "validation", **exc.context}
        raise
    try:
        changes = persist_snapshot(
            settings.database_url,
            repositories,
            alerts_by_repository,
            advisories,
            datetime.now(UTC),
        )
    except SyncError as exc:
        exc.context = {"stage": "persist", **exc.context}
        raise
    return {
        "api_version": GITHUB_API_VERSION,
        "repositories": summaries,
        "changes": changes,
        "db_applied": True,
    }
