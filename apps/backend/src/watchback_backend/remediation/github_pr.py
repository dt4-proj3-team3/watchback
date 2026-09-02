from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import tempfile
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name


GITHUB_API = "https://api.github.com"
REQUIRED_NPM_VERSION = "11.12.1"
REQUIRED_WORKFLOW_NAME = "Watchback remediation check"
NPM_FILENAMES = {"package.json", "package-lock.json"}
PIP_FILENAMES = {"pyproject.toml", "uv.lock"}
SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


class GitHubRemediationError(RuntimeError):
    pass


@dataclass(frozen=True)
class PullRequestResult:
    repository_full_name: str
    project_root: str
    number: int
    url: str
    head_ref: str
    base_ref: str
    head_sha: str
    current_version: str
    target_version: str
    changed_files: list[str]


@dataclass(frozen=True)
class PullRequestMergeResult:
    repository_full_name: str
    number: int
    url: str
    merged: bool
    merge_sha: str
    merged_at: str | None


@dataclass(frozen=True)
class PullRequestCloseResult:
    repository_full_name: str
    number: int
    url: str
    closed: bool
    closed_at: str | None


def close_package_update_pr(
    *, token: str, repository_full_name: str, number: int,
) -> PullRequestCloseResult:
    client = GitHubClient(token)
    pr = client.request("GET", f"/repos/{repository_full_name}/pulls/{number}")
    if pr.get("merged"):
        raise GitHubRemediationError("이미 병합된 PR은 닫을 수 없습니다.")
    if pr.get("state") == "open":
        pr = client.request(
            "PATCH",
            f"/repos/{repository_full_name}/pulls/{number}",
            {"state": "closed"},
        )
    if pr.get("state") != "closed":
        raise GitHubRemediationError("GitHub에서 PR을 닫지 못했습니다.")
    return PullRequestCloseResult(
        repository_full_name=repository_full_name,
        number=number,
        url=pr["html_url"],
        closed=True,
        closed_at=pr.get("closed_at"),
    )


def _semver(value: str) -> tuple[int, int, int] | None:
    match = SEMVER_RE.fullmatch(value or "")
    return tuple(map(int, match.groups())) if match else None


def require_version_upgrade(current: str, target: str) -> None:
    current_parts = _semver(current)
    target_parts = _semver(target)
    if not current_parts or not target_parts:
        raise GitHubRemediationError("현재 버전과 수정 버전은 정확한 semver여야 합니다.")
    if target_parts <= current_parts:
        raise GitHubRemediationError("수정 버전은 현재 버전보다 높아야 합니다.")


def require_patch_update(current: str, target: str) -> None:
    """이전 호출부 호환용 별칭. major·minor 업데이트도 허용한다."""
    require_version_upgrade(current, target)


def _dependency_paths(manifest_path: str | None) -> tuple[str, str, str]:
    normalized = (manifest_path or "package-lock.json").lstrip("/")
    parent = str(PurePosixPath(normalized).parent)
    project_root = "" if parent == "." else parent
    prefix = f"{project_root}/" if project_root else ""
    return project_root, f"{prefix}package.json", f"{prefix}package-lock.json"


def _python_dependency_paths(manifest_path: str | None) -> tuple[str, str, str]:
    normalized = (manifest_path or "pyproject.toml").lstrip("/")
    parent = str(PurePosixPath(normalized).parent)
    project_root = "" if parent == "." else parent
    prefix = f"{project_root}/" if project_root else ""
    return project_root, f"{prefix}pyproject.toml", f"{prefix}uv.lock"


def _allowed_paths(project_root: str, ecosystem: str) -> set[str]:
    prefix = f"{project_root}/" if project_root else ""
    filenames = PIP_FILENAMES if ecosystem.lower() == "pip" else NPM_FILENAMES
    return {f"{prefix}{name}" for name in filenames}


def _declared_version(payload: dict, package_name: str) -> str | None:
    for section in ("dependencies", "devDependencies", "optionalDependencies"):
        value = payload.get(section, {}).get(package_name)
        if value is not None:
            return value
    return None


class GitHubClient:
    def __init__(self, token: str):
        self._token = token

    def request(self, method: str, path: str, payload: dict | None = None) -> object:
        data = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(
            path if path.startswith("http") else f"{GITHUB_API}{path}",
            data=data,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self._token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "watchback-remediation-api",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                body = response.read()
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8", errors="replace")
            raise GitHubRemediationError(
                f"GitHub API 요청이 실패했습니다. HTTP {error.code}: {body[:300]}"
            ) from error
        except urllib.error.URLError as error:
            raise GitHubRemediationError("GitHub API에 연결할 수 없습니다.") from error

    def get_file(self, repository: str, path: str, ref: str) -> bytes:
        result = self.request(
            "GET",
            f"/repos/{repository}/contents/{urllib.parse.quote(path)}"
            f"?ref={urllib.parse.quote(ref)}",
        )
        return base64.b64decode(result["content"])  # type: ignore[index]


def merge_package_update_pr(
    *,
    token: str,
    repository_full_name: str,
    number: int,
    expected_head_ref: str,
    expected_head_sha: str,
    project_root: str,
    ecosystem: str = "npm",
) -> PullRequestMergeResult:
    client = GitHubClient(token)
    pr = client.request("GET", f"/repos/{repository_full_name}/pulls/{number}")
    if pr.get("merged"):
        return PullRequestMergeResult(
            repository_full_name=repository_full_name,
            number=number,
            url=pr["html_url"],
            merged=True,
            merge_sha=pr.get("merge_commit_sha") or expected_head_sha,
            merged_at=pr.get("merged_at"),
        )
    if pr.get("state") != "open":
        raise GitHubRemediationError("열린 PR만 병합할 수 있습니다.")
    if pr["head"]["ref"] != expected_head_ref or pr["head"]["sha"] != expected_head_sha:
        raise GitHubRemediationError("PR head가 조치 이력에 저장된 버전과 달라 병합을 중단했습니다.")
    if pr.get("mergeable") is False:
        raise GitHubRemediationError("GitHub에서 병합 불가능한 PR로 확인되었습니다.")

    files = client.request(
        "GET", f"/repos/{repository_full_name}/pulls/{number}/files?per_page=100"
    )
    allowed_paths = _allowed_paths(project_root, ecosystem)
    changed_paths = {item["filename"] for item in files}
    if not changed_paths or changed_paths - allowed_paths:
        raise GitHubRemediationError("PR에 자동조치 허용 범위 밖의 파일이 포함되어 있습니다.")

    query = urllib.parse.urlencode(
        {"event": "pull_request", "head_sha": expected_head_sha, "per_page": 100}
    )
    workflow_runs = client.request(
        "GET", f"/repos/{repository_full_name}/actions/runs?{query}"
    ).get("workflow_runs", [])
    required_runs = [
        run for run in workflow_runs if run.get("name") == REQUIRED_WORKFLOW_NAME
    ]
    incomplete = [
        run["name"] for run in required_runs if run.get("status") != "completed"
    ]
    failed = [
        run["name"]
        for run in required_runs
        if run.get("status") == "completed" and run.get("conclusion") != "success"
    ]
    if incomplete:
        raise GitHubRemediationError(f"아직 완료되지 않은 검사가 있습니다: {', '.join(incomplete)}")
    if failed:
        raise GitHubRemediationError(f"실패한 검사가 있습니다: {', '.join(failed)}")

    merged = client.request(
        "PUT",
        f"/repos/{repository_full_name}/pulls/{number}/merge",
        {"merge_method": "squash", "sha": expected_head_sha},
    )
    if not merged.get("merged"):
        raise GitHubRemediationError(
            f"GitHub이 PR 병합을 거부했습니다: {merged.get('message', '원인 미상')}"
        )
    refreshed = client.request("GET", f"/repos/{repository_full_name}/pulls/{number}")
    return PullRequestMergeResult(
        repository_full_name=repository_full_name,
        number=number,
        url=refreshed["html_url"],
        merged=True,
        merge_sha=merged["sha"],
        merged_at=refreshed.get("merged_at"),
    )


def _resolve_npm_update(
    package_json_bytes: bytes,
    package_lock_bytes: bytes,
    package_name: str,
    current_version: str,
    target_version: str,
) -> tuple[dict[str, bytes], list[str]]:
    require_version_upgrade(current_version, target_version)
    with tempfile.TemporaryDirectory(prefix="watchback-remediation-") as temp:
        root = Path(temp)
        workdir = root / "repository"
        workdir.mkdir()
        (workdir / "package.json").write_bytes(package_json_bytes)
        (workdir / "package-lock.json").write_bytes(package_lock_bytes)

        npm_version = subprocess.run(
            ["npm", "--version"], capture_output=True, text=True, check=True, timeout=30
        ).stdout.strip()
        if npm_version != REQUIRED_NPM_VERSION:
            raise GitHubRemediationError(
                f"npm {REQUIRED_NPM_VERSION}이 필요하지만 {npm_version}이 설치되어 있습니다."
            )
        before = {name: (workdir / name).read_bytes() for name in NPM_FILENAMES}
        environment = os.environ.copy()
        environment["npm_config_cache"] = str(root / "npm-cache")
        completed = subprocess.run(
            [
                "npm", "install", f"{package_name}@{target_version}", "--save-exact",
                "--package-lock-only", "--ignore-scripts", "--no-audit", "--no-fund",
            ],
            cwd=workdir,
            env=environment,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if completed.returncode:
            raise GitHubRemediationError(
                f"npm lockfile 갱신에 실패했습니다: {completed.stderr[-500:]}"
            )
        unexpected = {path.name for path in workdir.iterdir()} - NPM_FILENAMES
        if unexpected:
            raise GitHubRemediationError(f"허용되지 않은 파일이 생성되었습니다: {sorted(unexpected)}")
        changed = sorted(
            name for name, original in before.items() if (workdir / name).read_bytes() != original
        )
        if not changed or set(changed) - NPM_FILENAMES:
            raise GitHubRemediationError(f"허용된 변경 파일을 확인할 수 없습니다: {changed}")

        package_json = json.loads((workdir / "package.json").read_text())
        package_lock = json.loads((workdir / "package-lock.json").read_text())
        declared = _declared_version(package_json, package_name)
        root_locked = _declared_version(package_lock.get("packages", {}).get("", {}), package_name)
        locked = (package_lock.get("packages", {}).get(f"node_modules/{package_name}") or {}).get("version")
        if {declared, root_locked, locked} != {target_version}:
            raise GitHubRemediationError(
                "manifest와 lockfile의 목표 버전이 일치하지 않습니다."
            )
        return ({name: (workdir / name).read_bytes() for name in NPM_FILENAMES}, changed)


def _replace_python_requirement(
    pyproject_bytes: bytes, package_name: str, target_version: str
) -> bytes:
    text = pyproject_bytes.decode("utf-8")
    payload = tomllib.loads(text)
    dependencies = payload.get("project", {}).get("dependencies", [])
    matches = []
    for value in dependencies:
        try:
            requirement = Requirement(value)
        except ValueError:
            continue
        if canonicalize_name(requirement.name) == canonicalize_name(package_name):
            matches.append((value, requirement))
    if len(matches) != 1:
        raise GitHubRemediationError(
            "pyproject.toml의 runtime 직접 의존성을 하나로 확정할 수 없습니다."
        )
    original, requirement = matches[0]
    extras = f"[{','.join(sorted(requirement.extras))}]" if requirement.extras else ""
    marker = f"; {requirement.marker}" if requirement.marker else ""
    replacement = f"{requirement.name}{extras}=={target_version}{marker}"
    if text.count(original) != 1:
        raise GitHubRemediationError("pyproject.toml 의존성 선언 위치를 확정할 수 없습니다.")
    return text.replace(original, replacement, 1).encode("utf-8")


def _resolve_python_update(
    pyproject_bytes: bytes,
    uv_lock_bytes: bytes,
    package_name: str,
    current_version: str,
    target_version: str,
) -> tuple[dict[str, bytes], list[str]]:
    require_version_upgrade(current_version, target_version)
    with tempfile.TemporaryDirectory(prefix="watchback-remediation-") as temp:
        root = Path(temp)
        workdir = root / "repository"
        workdir.mkdir()
        (workdir / "pyproject.toml").write_bytes(
            _replace_python_requirement(pyproject_bytes, package_name, target_version)
        )
        (workdir / "uv.lock").write_bytes(uv_lock_bytes)
        before = {
            "pyproject.toml": pyproject_bytes,
            "uv.lock": uv_lock_bytes,
        }
        environment = os.environ.copy()
        environment["UV_CACHE_DIR"] = str(root / "uv-cache")
        completed = subprocess.run(
            ["uv", "lock", "--upgrade-package", f"{package_name}=={target_version}"],
            cwd=workdir,
            env=environment,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if completed.returncode:
            raise GitHubRemediationError(
                f"uv lockfile 갱신에 실패했습니다: {completed.stderr[-500:]}"
            )
        unexpected = {path.name for path in workdir.iterdir()} - PIP_FILENAMES
        if unexpected:
            raise GitHubRemediationError(
                f"허용되지 않은 파일이 생성되었습니다: {sorted(unexpected)}"
            )
        changed = sorted(
            name for name, original in before.items()
            if (workdir / name).read_bytes() != original
        )
        if not changed or set(changed) - PIP_FILENAMES:
            raise GitHubRemediationError(f"허용된 변경 파일을 확인할 수 없습니다: {changed}")
        updated_project = tomllib.loads((workdir / "pyproject.toml").read_text())
        updated_requirements = [
            Requirement(value)
            for value in updated_project.get("project", {}).get("dependencies", [])
        ]
        declared = [
            requirement for requirement in updated_requirements
            if canonicalize_name(requirement.name) == canonicalize_name(package_name)
        ]
        lock = tomllib.loads((workdir / "uv.lock").read_text())
        locked_versions = {
            str(item.get("version")) for item in lock.get("package", [])
            if canonicalize_name(str(item.get("name", ""))) == canonicalize_name(package_name)
        }
        if len(declared) != 1 or str(declared[0].specifier) != f"=={target_version}" or locked_versions != {target_version}:
            raise GitHubRemediationError(
                "pyproject.toml과 uv.lock의 목표 버전이 일치하지 않습니다."
            )
        return ({name: (workdir / name).read_bytes() for name in PIP_FILENAMES}, changed)


def create_package_update_pr(
    *,
    token: str,
    repository_full_name: str,
    manifest_path: str | None,
    package_name: str,
    current_version: str,
    target_version: str,
    cve_ids: list[str],
    alert_numbers: list[int],
    ecosystem: str = "npm",
) -> PullRequestResult:
    client = GitHubClient(token)
    repository = client.request("GET", f"/repos/{repository_full_name}")
    default_branch = repository["default_branch"]  # type: ignore[index]
    if ecosystem.lower() == "pip":
        project_root, manifest_file, lock_file = _python_dependency_paths(manifest_path)
        resolved, changed = _resolve_python_update(
            client.get_file(repository_full_name, manifest_file, default_branch),
            client.get_file(repository_full_name, lock_file, default_branch),
            package_name,
            current_version,
            target_version,
        )
    elif ecosystem.lower() == "npm":
        project_root, manifest_file, lock_file = _dependency_paths(manifest_path)
        resolved, changed = _resolve_npm_update(
            client.get_file(repository_full_name, manifest_file, default_branch),
            client.get_file(repository_full_name, lock_file, default_branch),
            package_name,
            current_version,
            target_version,
        )
    else:
        raise GitHubRemediationError(f"지원하지 않는 ecosystem입니다: {ecosystem}")
    files = {
        (f"{project_root}/{name}" if project_root else name): content
        for name, content in resolved.items()
    }
    slug = re.sub(r"[^a-z0-9-]+", "-", package_name.lower()).strip("-")
    branch = f"watchback/update-{slug}-{target_version}"
    owner = repository_full_name.split("/", 1)[0]
    query = urllib.parse.urlencode({"state": "open", "head": f"{owner}:{branch}"})
    existing = client.request("GET", f"/repos/{repository_full_name}/pulls?{query}")
    base_ref = client.request(
        "GET", f"/repos/{repository_full_name}/git/ref/heads/{urllib.parse.quote(default_branch)}"
    )
    base_sha = base_ref["object"]["sha"]  # type: ignore[index]
    try:
        client.request(
            "POST", f"/repos/{repository_full_name}/git/refs",
            {"ref": f"refs/heads/{branch}", "sha": base_sha},
        )
        parent_sha = base_sha
    except GitHubRemediationError as error:
        if "HTTP 422" not in str(error):
            raise
        branch_ref = client.request(
            "GET",
            f"/repos/{repository_full_name}/git/ref/heads/"
            f"{urllib.parse.quote(branch, safe='')}",
        )
        parent_sha = branch_ref["object"]["sha"]  # type: ignore[index]
    entries = []
    for path, content in sorted(files.items()):
        blob = client.request(
            "POST", f"/repos/{repository_full_name}/git/blobs",
            {"content": base64.b64encode(content).decode(), "encoding": "base64"},
        )
        entries.append({"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]})  # type: ignore[index]
    parent = client.request("GET", f"/repos/{repository_full_name}/git/commits/{parent_sha}")
    tree = client.request(
        "POST", f"/repos/{repository_full_name}/git/trees",
        {"base_tree": parent["tree"]["sha"], "tree": entries},  # type: ignore[index]
    )
    commit = client.request(
        "POST", f"/repos/{repository_full_name}/git/commits",
        {
            "message": f"fix(deps): update {package_name} to {target_version}",
            "tree": tree["sha"], "parents": [parent_sha],  # type: ignore[index]
        },
    )
    client.request(
        "PATCH",
        f"/repos/{repository_full_name}/git/refs/heads/{urllib.parse.quote(branch, safe='')}",
        {"sha": commit["sha"], "force": False},  # type: ignore[index]
    )
    if existing:
        pr = client.request(
            "GET", f"/repos/{repository_full_name}/pulls/{existing[0]['number']}"  # type: ignore[index]
        )
    else:
        cves = ", ".join(f"`{value}`" for value in sorted(set(cve_ids)))
        alerts = ", ".join(f"`#{value}`" for value in sorted(set(alert_numbers)))
        body = (
            "## Watchback 업데이트 PR\n\n"
            f"- 패키지: `{package_name}`\n"
            f"- 버전: `{current_version}` → `{target_version}`\n"
            f"- 관련 CVE: {cves}\n"
            f"- Dependabot Alert: {alerts}\n\n"
            "사용자가 Watchback에서 명시적으로 요청한 패키지 업데이트입니다. "
            "병합 전 CI와 애플리케이션 테스트 결과를 검토하세요."
        )
        pr = client.request(
            "POST", f"/repos/{repository_full_name}/pulls",
            {
                "title": f"fix(deps): update {package_name} to {target_version}",
                "head": branch, "base": default_branch, "body": body,
            },
        )
    return PullRequestResult(
        repository_full_name=repository_full_name,
        project_root=project_root,
        number=pr["number"],  # type: ignore[index]
        url=pr["html_url"],  # type: ignore[index]
        head_ref=branch,
        base_ref=default_branch,
        head_sha=commit["sha"],  # type: ignore[index]
        current_version=current_version,
        target_version=target_version,
        changed_files=[f"{project_root}/{name}" if project_root else name for name in changed],
    )
