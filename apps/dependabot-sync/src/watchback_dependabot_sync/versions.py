from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass
from datetime import datetime
from pathlib import PurePosixPath
from typing import Literal, Protocol

import yaml

from .github import GitHubClient, RepositoryFile
from .models import AlertPayload


ResolutionStatus = Literal["resolved", "multiple", "unavailable", "invalid"]
ResolutionReason = Literal[
    "unsupported_manifest",
    "lockfile_not_found",
    "package_not_found",
    "invalid_lockfile",
]
SUPPORTED_LOCKFILES = {
    "package-lock.json",
    "pnpm-lock.yaml",
    "pnpm-lock.yml",
    "yarn.lock",
    "uv.lock",
    "poetry.lock",
}


@dataclass(frozen=True)
class DependencyVersionResult:
    repository: str
    manifest_path: str | None
    commit_sha: str
    ecosystem: str
    package_name: str
    resolved_versions: tuple[str, ...]
    status: ResolutionStatus
    reason: ResolutionReason | None
    source_path: str | None
    source_blob_sha: str | None
    observed_at: datetime

    def as_dict(self) -> dict[str, object]:
        return {
            "repository": self.repository,
            "manifest_path": self.manifest_path,
            "commit_sha": self.commit_sha,
            "ecosystem": self.ecosystem,
            "package_name": self.package_name,
            "resolved_versions": list(self.resolved_versions),
            "status": self.status,
            "reason": self.reason,
            "source_path": self.source_path,
            "source_blob_sha": self.source_blob_sha,
            "observed_at": self.observed_at.isoformat(),
        }


class RepositoryFileReader(Protocol):
    def get_repository_file(
        self, full_name: str, path: str, *, ref: str
    ) -> RepositoryFile | None: ...


class RepositoryFileCache:
    def __init__(self, github: RepositoryFileReader) -> None:
        self._github = github
        self._files: dict[tuple[str, str, str], RepositoryFile | None] = {}

    def get(self, repository: str, path: str, commit_sha: str) -> RepositoryFile | None:
        key = (repository, path, commit_sha)
        if key not in self._files:
            self._files[key] = self._github.get_repository_file(
                repository, path, ref=commit_sha
            )
        return self._files[key]


def _normalize_python_package(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def _package_lock_versions(content: str, package_name: str) -> set[str]:
    payload = json.loads(content)
    if not isinstance(payload, dict):
        raise ValueError("package-lock root is not an object")
    versions: set[str] = set()

    packages = payload.get("packages")
    if isinstance(packages, dict):
        suffix = f"node_modules/{package_name}"
        for path, item in packages.items():
            if not isinstance(path, str) or not (
                path == suffix or path.endswith(f"/{suffix}")
            ):
                continue
            if isinstance(item, dict) and isinstance(item.get("version"), str):
                versions.add(item["version"])

    def visit_dependencies(value: object) -> None:
        if not isinstance(value, dict):
            return
        for name, item in value.items():
            if not isinstance(item, dict):
                continue
            version = item.get("version")
            if name == package_name and isinstance(version, str):
                versions.add(version)
            visit_dependencies(item.get("dependencies"))

    visit_dependencies(payload.get("dependencies"))
    return versions


def _toml_lock_versions(content: str, package_name: str) -> set[str]:
    payload = tomllib.loads(content)
    packages = payload.get("package")
    if not isinstance(packages, list):
        raise ValueError("TOML lockfile does not contain package records")
    normalized_name = _normalize_python_package(package_name)
    return {
        item["version"]
        for item in packages
        if isinstance(item, dict)
        and isinstance(item.get("name"), str)
        and _normalize_python_package(item["name"]) == normalized_name
        and isinstance(item.get("version"), str)
    }


def _pnpm_key_version(key: str, package_name: str) -> str | None:
    value = key.lstrip("/")
    if value.startswith("@"):
        if value.startswith(f"{package_name}@"):
            version = value[len(package_name) + 1 :]
        elif value.startswith(f"{package_name}/"):
            version = value[len(package_name) + 1 :]
        else:
            return None
    elif value.startswith(f"{package_name}@"):
        version = value[len(package_name) + 1 :]
    elif value.startswith(f"{package_name}/"):
        version = value[len(package_name) + 1 :]
    else:
        return None
    return version.split("(", 1)[0] or None


def _pnpm_lock_versions(content: str, package_name: str) -> set[str]:
    payload = yaml.safe_load(content)
    if not isinstance(payload, dict):
        raise ValueError("pnpm lockfile root is not an object")
    versions: set[str] = set()
    for section_name in ("packages", "snapshots"):
        section = payload.get(section_name)
        if not isinstance(section, dict):
            continue
        for key in section:
            if isinstance(key, str):
                version = _pnpm_key_version(key, package_name)
                if version:
                    versions.add(version)
    return versions


def _yarn_descriptor_matches(descriptor: str, package_name: str) -> bool:
    value = descriptor.strip().strip('"\'')
    if package_name.startswith("@"):
        return value.startswith(f"{package_name}@")
    return value.startswith(f"{package_name}@")


def _yarn_lock_versions(content: str, package_name: str) -> set[str]:
    versions: set[str] = set()
    matches_package = False
    for line in content.splitlines():
        if line and not line[0].isspace() and line.rstrip().endswith(":"):
            header = line.rstrip()[:-1]
            matches_package = any(
                _yarn_descriptor_matches(item, package_name)
                for item in header.split(",")
            )
            continue
        if not matches_package:
            continue
        match = re.match(r'^\s+version(?::|\s+)\s*["\']?([^"\'\s]+)', line)
        if match:
            versions.add(match.group(1))
            matches_package = False
    return versions


def _parse_versions(source: RepositoryFile, package_name: str) -> set[str]:
    filename = PurePosixPath(source.path).name
    if filename == "package-lock.json":
        return _package_lock_versions(source.content, package_name)
    if filename in {"uv.lock", "poetry.lock"}:
        return _toml_lock_versions(source.content, package_name)
    if filename in {"pnpm-lock.yaml", "pnpm-lock.yml"}:
        return _pnpm_lock_versions(source.content, package_name)
    if filename == "yarn.lock":
        return _yarn_lock_versions(source.content, package_name)
    raise ValueError("unsupported lockfile")


def _candidate_lockfiles(manifest_path: str | None, ecosystem: str) -> tuple[str, ...]:
    if not manifest_path:
        return ()
    path = PurePosixPath(manifest_path)
    if path.name in SUPPORTED_LOCKFILES:
        return (manifest_path,)
    parent = "" if str(path.parent) == "." else f"{path.parent}/"
    normalized_ecosystem = ecosystem.lower()
    if path.name == "package.json" or normalized_ecosystem == "npm":
        return tuple(
            f"{parent}{name}"
            for name in ("package-lock.json", "pnpm-lock.yaml", "yarn.lock")
        )
    if path.name == "pyproject.toml" or normalized_ecosystem in {
        "pip",
        "python",
    }:
        return (f"{parent}uv.lock", f"{parent}poetry.lock")
    return ()


def resolve_dependency_version(
    *,
    cache: RepositoryFileCache,
    repository: str,
    commit_sha: str,
    manifest_path: str | None,
    ecosystem: str,
    package_name: str,
    observed_at: datetime,
) -> DependencyVersionResult:
    source: RepositoryFile | None = None
    candidates = _candidate_lockfiles(manifest_path, ecosystem)
    for path in candidates:
        source = cache.get(repository, path, commit_sha)
        if source is not None:
            break
    if source is None:
        return DependencyVersionResult(
            repository=repository,
            manifest_path=manifest_path,
            commit_sha=commit_sha,
            ecosystem=ecosystem,
            package_name=package_name,
            resolved_versions=(),
            status="unavailable",
            reason="lockfile_not_found" if candidates else "unsupported_manifest",
            source_path=None,
            source_blob_sha=None,
            observed_at=observed_at,
        )
    try:
        versions = tuple(sorted(_parse_versions(source, package_name)))
    except (json.JSONDecodeError, tomllib.TOMLDecodeError, yaml.YAMLError, ValueError):
        return DependencyVersionResult(
            repository=repository,
            manifest_path=manifest_path,
            commit_sha=commit_sha,
            ecosystem=ecosystem,
            package_name=package_name,
            resolved_versions=(),
            status="invalid",
            reason="invalid_lockfile",
            source_path=source.path,
            source_blob_sha=source.blob_sha,
            observed_at=observed_at,
        )
    return DependencyVersionResult(
        repository=repository,
        manifest_path=manifest_path,
        commit_sha=commit_sha,
        ecosystem=ecosystem,
        package_name=package_name,
        resolved_versions=versions,
        status=("multiple" if len(versions) > 1 else "resolved")
        if versions
        else "unavailable",
        reason=None if versions else "package_not_found",
        source_path=source.path,
        source_blob_sha=source.blob_sha,
        observed_at=observed_at,
    )


def collect_dependency_versions(
    github: GitHubClient,
    repository: str,
    commit_sha: str,
    alerts: list[AlertPayload],
    observed_at: datetime,
) -> list[DependencyVersionResult]:
    cache = RepositoryFileCache(github)
    unique_dependencies = sorted(
        {
            (
                alert.dependency.manifest_path,
                alert.dependency.package.ecosystem,
                alert.dependency.package.name,
            )
            for alert in alerts
        },
        key=lambda item: (item[0] or "", item[1], item[2]),
    )
    return [
        resolve_dependency_version(
            cache=cache,
            repository=repository,
            commit_sha=commit_sha,
            manifest_path=manifest_path,
            ecosystem=ecosystem,
            package_name=package_name,
            observed_at=observed_at,
        )
        for manifest_path, ecosystem, package_name in unique_dependencies
    ]
