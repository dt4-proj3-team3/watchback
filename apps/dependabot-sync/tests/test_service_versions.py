from __future__ import annotations

from datetime import UTC, datetime

from watchback_dependabot_sync import service
from watchback_dependabot_sync.config import Settings
from watchback_dependabot_sync.github import RepositoryFile
from watchback_dependabot_sync.models import AlertPayload, RepositoryPayload


class FakeGitHub:
    def __init__(self, alert: AlertPayload) -> None:
        self.alert = alert

    def get_repository(self, full_name: str) -> RepositoryPayload:
        return RepositoryPayload(
            id=1,
            full_name=full_name,
            default_branch="main",
            updated_at=datetime(2026, 9, 1, tzinfo=UTC),
        )

    def get_alerts(self, full_name: str) -> tuple[list[AlertPayload], int]:
        return [self.alert], 1

    def get_commit_sha(self, full_name: str, ref: str) -> str:
        assert ref == "main"
        return "commit-sha"

    def get_repository_file(
        self, full_name: str, path: str, *, ref: str
    ) -> RepositoryFile | None:
        assert path == "package-lock.json"
        assert ref == "commit-sha"
        return RepositoryFile(
            path=path,
            blob_sha="blob-sha",
            content=(
                '{"lockfileVersion":3,"packages":'
                '{"node_modules/vite":{"version":"6.4.1"}}}'
            ),
        )


def test_run_sync_collects_versions_at_repository_commit(monkeypatch, raw_alerts):
    repository = "example/repo"
    alert = AlertPayload.model_validate(raw_alerts[0])
    persisted_versions = {}

    def persist(*args):
        persisted_versions.update(args[5])
        return {"advisories": {}, "alerts": {}, "dependency_versions": {}}

    monkeypatch.setattr(service, "REPOSITORIES", {repository: 1})
    monkeypatch.setattr(service, "verify_reference_data", lambda _: {})
    monkeypatch.setattr(service, "persist_snapshot", persist)

    result = service.run_sync(
        Settings(github_token="token", database_url="postgresql://unused"),
        client=FakeGitHub(alert),  # type: ignore[arg-type]
    )

    versions = result["repositories"][repository]["dependency_versions"]
    assert persisted_versions[repository][0].resolved_versions == ("6.4.1",)
    assert versions == [
        {
            "repository": repository,
            "manifest_path": "package-lock.json",
            "commit_sha": "commit-sha",
            "ecosystem": "npm",
            "package_name": "vite",
            "resolved_versions": ["6.4.1"],
            "status": "resolved",
            "reason": None,
            "source_path": "package-lock.json",
            "source_blob_sha": "blob-sha",
            "observed_at": versions[0]["observed_at"],
        }
    ]
