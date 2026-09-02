from types import SimpleNamespace

import pytest

from watchback_backend.remediation.github_pr import (
    GitHubClient,
    GitHubRemediationError,
    _dependency_paths,
    _python_dependency_paths,
    _replace_python_requirement,
    merge_package_update_pr,
    require_patch_update,
)
from watchback_backend.remediation.service import _is_supported_remediation_dependency


def test_patch_update_policy_accepts_same_major_minor() -> None:
    require_patch_update("7.5.1", "7.5.2")


@pytest.mark.parametrize("target", ["7.6.0", "8.0.0"])
def test_update_policy_accepts_minor_and_major_versions(target: str) -> None:
    require_patch_update("7.5.1", target)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        ("7.5.1", "7.5.1"),
        ("7.5.1", "7.4.9"),
        ("^7.5.1", "7.5.2"),
    ],
)
def test_patch_update_policy_rejects_broader_or_non_exact_changes(
    current: str, target: str
) -> None:
    with pytest.raises(GitHubRemediationError):
        require_patch_update(current, target)


def test_dependency_paths_keep_one_project_root() -> None:
    assert _dependency_paths("package-lock.json") == (
        "",
        "package.json",
        "package-lock.json",
    )
    assert _dependency_paths("apps/admin/package-lock.json") == (
        "apps/admin",
        "apps/admin/package.json",
        "apps/admin/package-lock.json",
    )
    assert _python_dependency_paths("uv.lock") == (
        "",
        "pyproject.toml",
        "uv.lock",
    )


def test_replaces_pep621_runtime_dependency_without_reformatting_manifest() -> None:
    original = b'''[project]\nname = "lab"\ndependencies = [\n  "BentoML==1.4.2",\n  "Django==4.2.20",\n]\n'''

    updated = _replace_python_requirement(original, "bentoml", "1.4.19")

    assert b'"BentoML==1.4.19"' in updated
    assert b'"Django==4.2.20"' in updated


@pytest.mark.parametrize(
    ("ecosystem", "manifest", "relationship", "expected"),
    [
        ("pip", "pyproject.toml", "unknown", True),
        ("pip", "uv.lock", "direct", True),
        ("pip", "uv.lock", "unknown", False),
        ("pip", "pyproject.toml", "transitive", False),
        ("npm", "package.json", "unknown", False),
    ],
)
def test_supported_dependency_treats_verified_python_manifest_as_direct(
    ecosystem: str,
    manifest: str,
    relationship: str,
    expected: bool,
) -> None:
    row = SimpleNamespace(
        ecosystem=ecosystem,
        manifest_path=manifest,
        dependency_scope="runtime",
        dependency_relationship=relationship,
    )

    assert _is_supported_remediation_dependency(row) is expected


def test_merge_uses_actions_workflow_runs_instead_of_checks_api(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    def request(_client, method: str, path: str, payload=None):
        calls.append((method, path))
        if path.endswith("/pulls/7"):
            return {
                "state": "open",
                "merged": False,
                "mergeable": True,
                "html_url": "https://github.com/example/lab/pull/7",
                "head": {"ref": "watchback/update", "sha": "head-sha"},
                "merged_at": None,
            }
        if path.endswith("/pulls/7/files?per_page=100"):
            return [{"filename": "package.json"}, {"filename": "package-lock.json"}]
        if "/actions/runs?" in path:
            return {
                "workflow_runs": [{
                    "name": "Watchback remediation check",
                    "status": "completed",
                    "conclusion": "success",
                }]
            }
        if method == "PUT" and path.endswith("/pulls/7/merge"):
            return {"merged": True, "sha": "merge-sha"}
        raise AssertionError(f"unexpected request: {method} {path}")

    monkeypatch.setattr(GitHubClient, "request", request)

    result = merge_package_update_pr(
        token="token",
        repository_full_name="example/lab",
        number=7,
        expected_head_ref="watchback/update",
        expected_head_sha="head-sha",
        project_root="",
    )

    assert result.merged is True
    assert any("/actions/runs?event=pull_request&head_sha=head-sha&per_page=100" in path for _, path in calls)
    assert all("check-runs" not in path for _, path in calls)


def test_merge_blocks_when_required_actions_workflow_failed(monkeypatch) -> None:
    def request(_client, method: str, path: str, payload=None):
        if path.endswith("/pulls/7"):
            return {
                "state": "open",
                "merged": False,
                "mergeable": True,
                "html_url": "https://github.com/example/lab/pull/7",
                "head": {"ref": "watchback/update", "sha": "head-sha"},
            }
        if path.endswith("/pulls/7/files?per_page=100"):
            return [{"filename": "package.json"}, {"filename": "package-lock.json"}]
        if "/actions/runs?" in path:
            return {
                "workflow_runs": [{
                    "name": "Watchback remediation check",
                    "status": "completed",
                    "conclusion": "failure",
                }]
            }
        raise AssertionError(f"unexpected request: {method} {path}")

    monkeypatch.setattr(GitHubClient, "request", request)

    with pytest.raises(GitHubRemediationError, match="실패한 검사가 있습니다"):
        merge_package_update_pr(
            token="token",
            repository_full_name="example/lab",
            number=7,
            expected_head_ref="watchback/update",
            expected_head_sha="head-sha",
            project_root="",
        )


def test_merge_allows_repository_without_required_actions_workflow(monkeypatch) -> None:
    def request(_client, method: str, path: str, payload=None):
        if path.endswith("/pulls/7"):
            return {
                "state": "open",
                "merged": False,
                "mergeable": True,
                "html_url": "https://github.com/example/lab/pull/7",
                "head": {"ref": "watchback/update", "sha": "head-sha"},
                "merged_at": None,
            }
        if path.endswith("/pulls/7/files?per_page=100"):
            return [{"filename": "package.json"}, {"filename": "package-lock.json"}]
        if "/actions/runs?" in path:
            return {"workflow_runs": []}
        if method == "PUT" and path.endswith("/pulls/7/merge"):
            return {"merged": True, "sha": "merge-sha"}
        raise AssertionError(f"unexpected request: {method} {path}")

    monkeypatch.setattr(GitHubClient, "request", request)

    result = merge_package_update_pr(
        token="token",
        repository_full_name="example/lab",
        number=7,
        expected_head_ref="watchback/update",
        expected_head_sha="head-sha",
        project_root="",
    )

    assert result.merged is True
