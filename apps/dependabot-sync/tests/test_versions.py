from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime

import pytest

from watchback_dependabot_sync.github import RepositoryFile
from watchback_dependabot_sync.versions import (
    RepositoryFileCache,
    resolve_dependency_version,
)


NOW = datetime(2026, 9, 1, tzinfo=UTC)


class FakeGitHub:
    def __init__(self, files: dict[str, str]) -> None:
        self.files = files
        self.calls: Counter[str] = Counter()

    def get_repository_file(
        self, repository: str, path: str, *, ref: str
    ) -> RepositoryFile | None:
        assert repository == "example/repo"
        assert ref == "commit-sha"
        self.calls[path] += 1
        content = self.files.get(path)
        if content is None:
            return None
        return RepositoryFile(path=path, blob_sha=f"blob-{path}", content=content)


def resolve(
    github: FakeGitHub,
    *,
    manifest_path: str,
    ecosystem: str,
    package_name: str,
):
    return resolve_dependency_version(
        cache=RepositoryFileCache(github),
        repository="example/repo",
        commit_sha="commit-sha",
        manifest_path=manifest_path,
        ecosystem=ecosystem,
        package_name=package_name,
        observed_at=NOW,
    )


def test_package_lock_preserves_multiple_resolved_versions():
    github = FakeGitHub(
        {
            "package-lock.json": """
            {
              "lockfileVersion": 3,
              "packages": {
                "node_modules/vite": {"version": "6.4.1"},
                "node_modules/example/node_modules/vite": {"version": "5.4.0"}
              }
            }
            """
        }
    )

    result = resolve(
        github,
        manifest_path="package-lock.json",
        ecosystem="npm",
        package_name="vite",
    )

    assert result.status == "multiple"
    assert result.reason is None
    assert result.resolved_versions == ("5.4.0", "6.4.1")
    assert result.source_path == "package-lock.json"
    assert result.source_blob_sha == "blob-package-lock.json"


@pytest.mark.parametrize(
    ("manifest_path", "lockfile", "content", "package_name", "versions"),
    [
        (
            "pyproject.toml",
            "uv.lock",
            '[[package]]\nname = "litellm"\nversion = "1.81.16"\n',
            "LiteLLM",
            ("1.81.16",),
        ),
        (
            "services/api/pyproject.toml",
            "services/api/poetry.lock",
            '[[package]]\nname = "django"\nversion = "5.2.1"\n',
            "Django",
            ("5.2.1",),
        ),
        (
            "pnpm-lock.yaml",
            "pnpm-lock.yaml",
            "lockfileVersion: '9.0'\npackages:\n  vite@6.4.1: {}\n  vite@5.4.0: {}\n",
            "vite",
            ("5.4.0", "6.4.1"),
        ),
        (
            "yarn.lock",
            "yarn.lock",
            'vite@^6.0.0:\n  version "6.4.1"\n\n' "vite@^5.0.0:\n  version \"5.4.0\"\n",
            "vite",
            ("5.4.0", "6.4.1"),
        ),
    ],
)
def test_supported_lockfiles_are_resolved(
    manifest_path, lockfile, content, package_name, versions
):
    github = FakeGitHub({lockfile: content})
    result = resolve(
        github,
        manifest_path=manifest_path,
        ecosystem="pip" if manifest_path.endswith("pyproject.toml") else "npm",
        package_name=package_name,
    )
    assert result.resolved_versions == versions
    assert result.status == ("multiple" if len(versions) > 1 else "resolved")


def test_pyproject_uses_sibling_lockfile_and_file_cache_is_commit_scoped():
    github = FakeGitHub(
        {"services/api/uv.lock": '[[package]]\nname = "django"\nversion = "5.2.1"\n'}
    )
    cache = RepositoryFileCache(github)

    for package_name in ("django", "missing"):
        resolve_dependency_version(
            cache=cache,
            repository="example/repo",
            commit_sha="commit-sha",
            manifest_path="services/api/pyproject.toml",
            ecosystem="pip",
            package_name=package_name,
            observed_at=NOW,
        )

    assert github.calls == {"services/api/uv.lock": 1}


def test_missing_or_invalid_lockfile_is_explicitly_unavailable():
    missing = resolve(
        FakeGitHub({}),
        manifest_path="pyproject.toml",
        ecosystem="pip",
        package_name="django",
    )
    assert missing.status == "unavailable"
    assert missing.reason == "lockfile_not_found"
    assert missing.resolved_versions == ()
    assert missing.source_path is None

    invalid = resolve(
        FakeGitHub({"package-lock.json": "not-json"}),
        manifest_path="package-lock.json",
        ecosystem="npm",
        package_name="vite",
    )
    assert invalid.status == "invalid"
    assert invalid.reason == "invalid_lockfile"
    assert invalid.source_path == "package-lock.json"


def test_declared_range_is_not_reported_as_an_installed_version():
    result = resolve(
        FakeGitHub({"pyproject.toml": '[project]\ndependencies = ["django>=5"]'}),
        manifest_path="pyproject.toml",
        ecosystem="pip",
        package_name="django",
    )
    assert result.status == "unavailable"
    assert result.reason == "lockfile_not_found"
    assert result.resolved_versions == ()
