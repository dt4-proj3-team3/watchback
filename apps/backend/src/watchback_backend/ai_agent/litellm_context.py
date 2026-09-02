from __future__ import annotations

import json
import re
import tomllib
import urllib.request
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import PurePosixPath
from typing import Callable
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from watchback_backend.ai_agent.service import GroundingSource
from watchback_backend.api.service import RequestContext
from watchback_backend.db.models import AIContextDocument
from watchback_backend.remediation.github_pr import GitHubClient
from watchback_backend.remediation.github_pr import GitHubRemediationError
from watchback_backend.remediation.service import list_remediation_groups


LITELLM_PACKAGE = "litellm"
PYPI_JSON = "https://pypi.org/pypi/litellm/{version}/json"
PYPI_PAGE = "https://pypi.org/project/litellm/{version}/"
RELEASE_TAG = "v{version}-stable"
RELEASE_PATH = "/repos/BerriAI/litellm/releases/tags/{tag}"
MAX_SOURCE_FILES = 200
MAX_FILE_BYTES = 200_000

ANALYZED_SUFFIXES = {".py", ".toml", ".yaml", ".yml", ".json"}
ANALYZED_NAMES = {"dockerfile", "compose.yaml", "compose.yml"}
EXCLUDED_NAMES = {
    "readme.md",
    "package-lock.json",
    "pnpm-lock.yaml",
    "uv.lock",
    "yarn.lock",
}

VULNERABILITY_INDICATORS = {
    "CVE-2026-35029": {
        "label": "Proxy 설정 변경 기능",
        "terms": (
            "/config/update",
            "pass_through_endpoints",
            "ui_username",
            "ui_password",
        ),
    },
    "CVE-2026-40217": {
        "label": "Custom Code Guardrail",
        "terms": ("test_custom_code", "custom_code", "guardrails"),
    },
    "CVE-2026-42208": {
        "label": "Proxy API 키 검증 경로",
        "terms": (
            "disable_error_logs",
            "database_url",
            "litellm --config",
            "proxy_server",
        ),
    },
    "CVE-2026-42271": {
        "label": "MCP stdio 테스트 기능",
        "terms": ("mcp_servers", "mcp-rest", "test/connection", "stdio"),
    },
}

CURATED_ANSWERS = {
    "이 업데이트로 어떤 문제가 해결되나요?": """LiteLLM을 `1.81.16`에서 `1.83.11`로 업데이트하면 **저장소 2곳의 Open Alert 16건과 취약점 4건을 함께 조치**할 수 있습니다. [1][6]

- 프록시 설정 권한 검증 취약점 [2]
- Custom Code Guardrail 샌드박스 탈출 취약점 [3]
- Proxy API 키 검증 SQL 주입 취약점 [4]
- MCP stdio 테스트 명령 실행 취약점 [5]

업데이트 전 **Python `>=3.10,<3.14` 조건**을 확인하고, 적용 후 **Proxy·Guardrail·MCP 기능을 테스트**해야 합니다. [6]""",
    "우리 저장소에서 이 취약점들의 발생 조건이 확인되나요?": """`CVE-2026-42208`과 관련된 **LiteLLM Proxy 사용 단서**가 `app/proxy.py`에서 확인되었습니다. [7]

다만 이는 **정적 코드 검색으로 확인한 단서**이며, 취약한 API 키 검증 경로의 실제 호출이나 외부 노출까지 확인한 결과는 아닙니다.

나머지 3개 취약점은 관련 기능의 코드나 설정이 없어 **현재 저장소 정보만으로 사용 여부를 판단할 수 없습니다.** [7]""",
    "업데이트할 때 확인할 변경사항이 있나요?": """LiteLLM `1.83.11`은 **Python `>=3.10,<3.14`**를 요구합니다. 현재 두 저장소의 Python 버전은 이 범위에 포함됩니다. [6]

업데이트 후에는 다음 기능을 확인하는 것이 좋습니다.

- **Proxy 설정 변경과 API 키 인증**
- **Custom Code Guardrail 실행**
- **MCP stdio 연결 및 도구 조회**
- 기존 LLM 요청과 오류 처리

공식 Release Note에서는 전체 호환성 변경을 확인할 수 없으므로, **테스트 환경에서 기존 호출과 설정을 검증**해야 합니다. [6]""",
    "이 취약점들은 어떤 조건에서 문제가 되나요?": """- `CVE-2026-35029`: 인증된 사용자가 관리자 권한 없이 **Proxy 설정 변경 API**를 호출할 수 있을 때 문제가 됩니다. 설정 변경, 파일 읽기 및 권한 상승으로 이어질 수 있습니다. [2]

- `CVE-2026-40217`: 관리자 사용자가 **Custom Code Guardrail 테스트 API**에 Python 코드를 전달할 때 샌드박스를 벗어나 임의 코드를 실행할 수 있습니다. [3]

- `CVE-2026-42208`: 인증되지 않은 요청이 조작된 API 키로 취약한 검증 경로에 도달하면 **SQL 주입**이 발생할 수 있습니다. [4]

- `CVE-2026-42271`: 낮은 권한의 인증 사용자가 **MCP stdio 테스트 API**에 명령을 전달하면 Proxy 호스트에서 해당 명령이 실행될 수 있습니다. [5]

이 조건은 Advisory에 정의된 일반적인 발생 조건이며, 현재 저장소에서는 `CVE-2026-42208`과 관련된 **Proxy 사용 단서만 확인**되었습니다. [7]""",
}


def _fetch_json(url: str) -> dict:
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "watchback-ai-context"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def _version_parts(value: str) -> tuple[int, int, int] | None:
    match = re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", value)
    return tuple(map(int, match.groups())) if match else None


def version_change_level(current: str, target: str) -> str:
    current_parts = _version_parts(current)
    target_parts = _version_parts(target)
    if current_parts is None or target_parts is None:
        return "unknown"
    if current_parts[0] != target_parts[0]:
        return "major"
    if current_parts[1] != target_parts[1]:
        return "minor"
    return "patch"


def _analyzed_path(path: str) -> bool:
    name = PurePosixPath(path).name
    suffix = PurePosixPath(path).suffix.lower()
    return (
        name.lower() not in EXCLUDED_NAMES
        and (suffix in ANALYZED_SUFFIXES or name.lower() in ANALYZED_NAMES)
    )


def _declared_runtime(content: str) -> str | None:
    try:
        payload = tomllib.loads(content)
    except tomllib.TOMLDecodeError:
        return None
    value = payload.get("project", {}).get("requires-python")
    return str(value) if value else None


def _declares_litellm(content: str) -> bool:
    try:
        payload = tomllib.loads(content)
    except tomllib.TOMLDecodeError:
        return False
    dependencies = payload.get("project", {}).get("dependencies", [])
    return any(
        re.match(r"(?i)^\s*litellm(?:\[.*?\])?\s*(?:[<>=!~]|$)", str(value))
        for value in dependencies
    )


def scan_repository(
    client: GitHubClient,
    repository_full_name: str,
) -> dict:
    repository = client.request("GET", f"/repos/{repository_full_name}")
    default_branch = str(repository["default_branch"])
    commit = client.request(
        "GET", f"/repos/{repository_full_name}/commits/{default_branch}"
    )
    commit_sha = str(commit["sha"])
    tree = client.request(
        "GET",
        f"/repos/{repository_full_name}/git/trees/{commit_sha}?recursive=1",
    )
    selected = [
        item
        for item in tree.get("tree", [])
        if item.get("type") == "blob"
        and int(item.get("size") or 0) <= MAX_FILE_BYTES
        and _analyzed_path(str(item.get("path") or ""))
    ][:MAX_SOURCE_FILES]

    findings: list[dict] = []
    dependency_declared = False
    repository_runtime = None
    for item in selected:
        path = str(item["path"])
        content = client.get_file(repository_full_name, path, commit_sha).decode(
            "utf-8", errors="replace"
        )
        if PurePosixPath(path).name == "pyproject.toml":
            dependency_declared = dependency_declared or _declares_litellm(content)
            repository_runtime = repository_runtime or _declared_runtime(content)
        for line_number, line in enumerate(content.splitlines(), 1):
            normalized = line.lower()
            for cve_id, rule in VULNERABILITY_INDICATORS.items():
                for term in rule["terms"]:
                    if str(term).lower() not in normalized:
                        continue
                    findings.append(
                        {
                            "cve_id": cve_id,
                            "indicator": rule["label"],
                            "matched_term": term,
                            "path": path,
                            "line": line_number,
                        }
                    )

    return {
        "repository": repository_full_name,
        "commit_sha": commit_sha,
        "dependency_declared": dependency_declared,
        "repository_requires_python": repository_runtime,
        "analyzed_files": [str(item["path"]) for item in selected],
        "findings": findings,
    }


def build_usage_payload(repository_results: list[dict]) -> dict:
    cves = []
    for cve_id, rule in VULNERABILITY_INDICATORS.items():
        matches = [
            {"repository": item["repository"], **finding}
            for item in repository_results
            for finding in item["findings"]
            if finding["cve_id"] == cve_id
        ]
        cves.append(
            {
                "cve_id": cve_id,
                "condition": rule["label"],
                "status": "condition_clue_found" if matches else "insufficient",
                "matches": matches,
            }
        )
    return {
        "analysis_kind": "configuration_clues",
        "limitations": (
            "정적 문자열 검색 결과이며 코드 도달성, 외부 노출 또는 실제 악용 가능성을 "
            "판정하지 않습니다."
        ),
        "repositories": repository_results,
        "vulnerabilities": cves,
    }


def _release_keywords(body: str) -> dict:
    lower = body.lower()
    return {
        "breaking_change_mentioned": "breaking" in lower,
        "deprecation_mentioned": "deprecat" in lower,
        "python_requirement_mentioned": "python" in lower,
    }


def upgrade_source_url(release: dict, target_version: str) -> str:
    return str(release.get("html_url") or "") or PYPI_PAGE.format(
        version=target_version
    )


def build_upgrade_payload(
    *,
    current_version: str,
    target_version: str,
    current_pypi: dict,
    target_pypi: dict,
    repository_results: list[dict],
    release: dict,
    vulnerabilities: list[dict],
) -> dict:
    release_body = str(release.get("body") or "")
    return {
        "current_version": current_version,
        "target_version": target_version,
        "version_change_level": version_change_level(current_version, target_version),
        "current_requires_python": current_pypi.get("info", {}).get("requires_python"),
        "target_requires_python": target_pypi.get("info", {}).get("requires_python"),
        "repository_runtime_constraints": [
            {
                "repository": item["repository"],
                "requires_python": item["repository_requires_python"],
            }
            for item in repository_results
        ],
        "official_release": {
            "url": release.get("html_url"),
            "published_at": release.get("published_at"),
            **_release_keywords(release_body),
        },
        "dependabot_patch_candidates": vulnerabilities,
        "curated_answers": CURATED_ANSWERS,
        "limitations": (
            "공식 PyPI 메타데이터와 해당 버전 Release Note의 명시적 표현만 확인했으며 "
            "전체 API 호환성이나 패치 안전성을 보장하지 않습니다."
        ),
    }


def _upsert_document(
    session: Session,
    context: RequestContext,
    group,
    document_type: str,
    content: dict,
    source_revision: str,
    source_url: str | None,
    generated_at: datetime,
) -> AIContextDocument:
    row = session.scalar(
        select(AIContextDocument).where(
            AIContextDocument.organization_id == context.organization_id,
            AIContextDocument.group_key == group.id,
            AIContextDocument.document_type == document_type,
        )
    )
    if row is None:
        row = AIContextDocument(
            id=uuid4(),
            organization_id=context.organization_id,
            group_key=group.id,
            document_type=document_type,
        )
        session.add(row)
    row.ecosystem = group.ecosystem
    row.package_name = group.package_name
    row.content = content
    row.source_revision = source_revision
    row.source_url = source_url
    row.generated_at = generated_at
    session.flush()
    return row


def backfill_litellm_context(
    session: Session,
    context: RequestContext,
    github_token: str,
    *,
    client: GitHubClient | None = None,
    fetch_json: Callable[[str], dict] = _fetch_json,
    now: datetime | None = None,
) -> list[AIContextDocument]:
    group = next(
        (
            item
            for item in list_remediation_groups(session, context).items
            if item.ecosystem.lower() == "pip"
            and item.package_name.lower().replace("_", "-") == LITELLM_PACKAGE
        ),
        None,
    )
    if group is None:
        raise ValueError("LiteLLM 조치 그룹을 찾을 수 없습니다.")
    current_versions = sorted(
        {version for target in group.targets for version in target.current_versions}
    )
    if len(current_versions) != 1 or not group.representative_patched_version:
        raise ValueError("LiteLLM 현재·권장 버전을 하나로 확정할 수 없습니다.")
    current_version = current_versions[0]
    target_version = group.representative_patched_version
    github = client or GitHubClient(github_token)
    repository_results = [
        scan_repository(github, target.repository.full_name)
        for target in group.targets
    ]
    usage_payload = build_usage_payload(repository_results)

    current_pypi = fetch_json(PYPI_JSON.format(version=current_version))
    target_pypi = fetch_json(PYPI_JSON.format(version=target_version))
    tag = RELEASE_TAG.format(version=target_version)
    try:
        release = github.request("GET", RELEASE_PATH.format(tag=tag))
    except GitHubRemediationError:
        release = {}
    vulnerabilities = [
        {
            "cve_id": item.cve_id,
            "title": item.advisory_summary,
            "first_patched_versions": sorted(
                {
                    alert.first_patched_version
                    for target in group.targets
                    for alert in target.alerts
                    if alert.cve_id == item.cve_id and alert.first_patched_version
                }
            ),
        }
        for item in group.vulnerabilities
    ]
    upgrade_payload = build_upgrade_payload(
        current_version=current_version,
        target_version=target_version,
        current_pypi=current_pypi,
        target_pypi=target_pypi,
        repository_results=repository_results,
        release=release,
        vulnerabilities=vulnerabilities,
    )
    generated_at = now or datetime.now(UTC)
    source_url = upgrade_source_url(release, target_version)
    revisions = sorted(item["commit_sha"] for item in repository_results)
    usage_revision = sha256("\n".join(revisions).encode()).hexdigest()
    documents = [
        _upsert_document(
            session,
            context,
            group,
            "usage_indicators",
            usage_payload,
            usage_revision,
            None,
            generated_at,
        ),
        _upsert_document(
            session,
            context,
            group,
            "upgrade_notes",
            upgrade_payload,
            f"{current_version}->{target_version}",
            source_url,
            generated_at,
        ),
    ]
    session.commit()
    return documents


def document_grounding_source(
    document: AIContextDocument,
    organization_id,
) -> GroundingSource:
    content = document.content
    if document.document_type == "usage_indicators":
        repositories = content.get("repositories", [])
        cves = content.get("vulnerabilities", [])
        found = [item for item in cves if item.get("status") == "condition_clue_found"]
        analyzed_files = sum(len(item.get("analyzed_files", [])) for item in repositories)
        text = (
            f"LiteLLM 의존성 선언 저장소={len(repositories)}곳; "
            f"분석 파일={analyzed_files}개; "
            f"발생 조건 단서가 확인된 CVE={len(found)}건; "
            f"CVE별 결과={json.dumps(cves, ensure_ascii=False)}; "
            f"한계={content.get('limitations')}"
        )
        title = "LiteLLM 저장소 취약 조건 단서"
        source_type = "usage_analysis"
    else:
        text = (
            f"버전={content.get('current_version')} → {content.get('target_version')}; "
            f"변경 수준={content.get('version_change_level')}; "
            f"Python 요구사항={content.get('current_requires_python')} → "
            f"{content.get('target_requires_python')}; "
            f"저장소 런타임={json.dumps(content.get('repository_runtime_constraints', []), ensure_ascii=False)}; "
            f"공식 Release 확인={json.dumps(content.get('official_release', {}), ensure_ascii=False)}; "
            "Dependabot Alert의 CVE별 최초 패치 후보="
            f"{json.dumps(content.get('dependabot_patch_candidates', []), ensure_ascii=False)}; "
            f"한계={content.get('limitations')}"
        )
        title = "LiteLLM 업데이트 검토 정보"
        source_type = "upgrade_analysis"
    return GroundingSource(
        organization_id=organization_id,
        source_type=source_type,
        source_id=f"ai_context:{document.id}",
        title=title,
        content=text,
        observed_at=document.generated_at,
        source_url=document.source_url,
    )
