from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from watchback_backend.ai_agent.litellm_context import (
    build_upgrade_payload,
    build_usage_payload,
    document_grounding_source,
    scan_repository,
    upgrade_source_url,
    version_change_level,
)


class FakeGitHubClient:
    def request(self, method: str, path: str):
        assert method == "GET"
        if path == "/repos/example/backend":
            return {"default_branch": "main"}
        if path == "/repos/example/backend/commits/main":
            return {"sha": "abc123"}
        if path == "/repos/example/backend/git/trees/abc123?recursive=1":
            return {
                "tree": [
                    {"type": "blob", "path": "pyproject.toml", "size": 120},
                    {"type": "blob", "path": "app/config.py", "size": 80},
                    {"type": "blob", "path": "README.md", "size": 80},
                ]
            }
        raise AssertionError(path)

    def get_file(self, repository: str, path: str, ref: str) -> bytes:
        assert repository == "example/backend"
        assert ref == "abc123"
        if path == "pyproject.toml":
            return b'[project]\nrequires-python = ">=3.10"\ndependencies = ["litellm==1.81.16"]\n'
        if path == "app/config.py":
            return b'proxy_server = "https://example.invalid"\n'
        raise AssertionError(path)


def test_scan_repository_records_conditions_without_source_snippets() -> None:
    result = scan_repository(FakeGitHubClient(), "example/backend")

    assert result["dependency_declared"] is True
    assert result["repository_requires_python"] == ">=3.10"
    assert result["analyzed_files"] == ["pyproject.toml", "app/config.py"]
    assert result["findings"] == [
        {
            "cve_id": "CVE-2026-42208",
            "indicator": "Proxy API 키 검증 경로",
            "matched_term": "proxy_server",
            "path": "app/config.py",
            "line": 1,
        }
    ]
    assert "snippet" not in result["findings"][0]


def test_usage_payload_does_not_treat_missing_clue_as_not_used() -> None:
    payload = build_usage_payload(
        [
            {
                "repository": "example/backend",
                "commit_sha": "abc123",
                "dependency_declared": True,
                "repository_requires_python": ">=3.10",
                "analyzed_files": ["pyproject.toml"],
                "findings": [],
            }
        ]
    )

    assert {item["status"] for item in payload["vulnerabilities"]} == {
        "insufficient"
    }
    assert "판정하지 않습니다" in payload["limitations"]


def test_upgrade_payload_keeps_official_facts_and_unknowns_separate() -> None:
    payload = build_upgrade_payload(
        current_version="1.81.16",
        target_version="1.83.11",
        current_pypi={"info": {"requires_python": ">=3.9,<4.0"}},
        target_pypi={"info": {"requires_python": ">=3.10,<3.14"}},
        repository_results=[
            {
                "repository": "example/backend",
                "repository_requires_python": ">=3.10",
            }
        ],
        release={
            "html_url": "https://github.com/BerriAI/litellm/releases/tag/v1.83.11-stable",
            "published_at": "2026-08-01T00:00:00Z",
            "body": "Docker image signature verification",
        },
        vulnerabilities=[{"cve_id": "CVE-2026-42208"}],
    )

    assert version_change_level("1.81.16", "1.83.11") == "minor"
    assert payload["target_requires_python"] == ">=3.10,<3.14"
    assert payload["repository_runtime_constraints"][0]["requires_python"] == ">=3.10"
    assert payload["official_release"]["breaking_change_mentioned"] is False
    assert payload["dependabot_patch_candidates"] == [
        {"cve_id": "CVE-2026-42208"}
    ]
    assert set(payload["curated_answers"]) == {
        "이 업데이트로 어떤 문제가 해결되나요?",
        "우리 저장소에서 이 취약점들의 발생 조건이 확인되나요?",
        "업데이트할 때 확인할 변경사항이 있나요?",
        "이 취약점들은 어떤 조건에서 문제가 되나요?",
    }
    answers = payload["curated_answers"]
    assert "**저장소 2곳의 Open Alert 16건과 취약점 4건을 함께 조치**" in answers[
        "이 업데이트로 어떤 문제가 해결되나요?"
    ]
    assert "**LiteLLM Proxy 사용 단서**" in answers[
        "우리 저장소에서 이 취약점들의 발생 조건이 확인되나요?"
    ]
    assert "**Python `>=3.10,<3.14`**" in answers[
        "업데이트할 때 확인할 변경사항이 있나요?"
    ]
    assert "**SQL 주입**" in answers["이 취약점들은 어떤 조건에서 문제가 되나요?"]
    assert "security_changes" not in payload


def test_upgrade_source_uses_pypi_when_release_is_missing() -> None:
    assert upgrade_source_url({}, "1.83.11") == (
        "https://pypi.org/project/litellm/1.83.11/"
    )


def test_ai_context_document_becomes_a_user_facing_grounding_source() -> None:
    document = SimpleNamespace(
        id=uuid4(),
        document_type="usage_indicators",
        content={
            "repositories": [{"analyzed_files": ["pyproject.toml"]}],
            "vulnerabilities": [
                {"cve_id": "CVE-2026-42208", "status": "insufficient"}
            ],
            "limitations": "실제 도달성을 판정하지 않습니다.",
        },
        generated_at=datetime(2026, 9, 2, tzinfo=UTC),
        source_url=None,
    )

    source = document_grounding_source(document, uuid4())

    assert source.source_type == "usage_analysis"
    assert source.title == "LiteLLM 저장소 취약 조건 단서"
    assert "insufficient" in source.content
