from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from watchback_backend.ai_agent import context as ai_context
from watchback_backend.api.schemas import (
    DETAIL_EXAMPLE,
    LIST_EXAMPLE,
    ReviewCaseDetail,
    ReviewCaseListResponse,
)
from watchback_backend.api.service import RequestContext


def test_case_context_contains_case_alert_candidates_evidence_and_annotations(
    monkeypatch,
) -> None:
    organization_id = uuid4()
    case_id = uuid4()
    detail = ReviewCaseDetail.model_validate(DETAIL_EXAMPLE)
    request_context = RequestContext(organization_id, uuid4(), "검토자")
    monkeypatch.setattr(
        ai_context.review_service,
        "get_review_case",
        lambda session, context, requested_case_id: detail,
    )

    sources = ai_context.build_grounding_sources(
        object(), request_context, case_id
    )

    assert {source.source_type for source in sources} >= {
        "review_case",
        "dependabot_alert",
        "candidate",
        "evidence",
        "source_annotation",
    }
    assert all(source.organization_id == organization_id for source in sources)
    assert len({source.source_id for source in sources}) == len(sources)
    evidence = next(source for source in sources if source.source_type == "evidence")
    assert "이전 값=false" in evidence.content
    assert "현재 값=true" in evidence.content
    alert = next(source for source in sources if source.source_type == "dependabot_alert")
    assert "영향 버전=< 2.0.1" in alert.content


def test_general_context_uses_only_top_three_open_cases(monkeypatch) -> None:
    organization_id = uuid4()
    request_context = RequestContext(organization_id, uuid4(), "검토자")
    item = LIST_EXAMPLE["items"][0]
    response = ReviewCaseListResponse.model_validate(
        {
            "items": [
                {**item, "id": f"30000000-0000-0000-0000-00000000000{index}"}
                for index in range(1, 4)
            ],
            "page": 1,
            "page_size": 3,
            "total": 10,
        }
    )
    captured = {}

    def fake_list(session, context, **kwargs):
        captured.update(kwargs)
        return response

    monkeypatch.setattr(ai_context.review_service, "list_review_cases", fake_list)

    sources = ai_context.build_grounding_sources(object(), request_context, None)

    assert captured["case_status"].value == "open"
    assert captured["sort"].value == "priority"
    assert captured["page_size"] == 3
    assert len([source for source in sources if source.source_type == "review_case"]) == 3
    assert len([source for source in sources if source.source_type == "candidate"]) == 3


def test_package_context_keeps_all_candidate_history_and_target_versions(
    monkeypatch,
) -> None:
    organization_id = uuid4()
    request_context = RequestContext(organization_id, uuid4(), "검토자")
    detail = ReviewCaseDetail.model_validate(DETAIL_EXAMPLE)
    candidates = [detail.candidates[0], detail.candidates[0].model_copy(update={"id": uuid4()})]
    alert = SimpleNamespace(
        **detail.alert.model_dump(),
        cve_id=detail.advisory.cve_id,
    )
    group_id = "a" * 64
    group = SimpleNamespace(
        id=group_id,
        package_name="example-package",
        ecosystem="npm",
        priority="P0",
        cve_count=1,
        repository_count=1,
        github_alert_counts=SimpleNamespace(open=1),
        recommended_fix_versions=["2.0.1"],
        updated_at=detail.updated_at,
        targets=[SimpleNamespace(
            current_versions=["1.9.0"],
            repository=detail.repository,
            manifest_path=detail.alert.manifest_path,
            alerts=[alert],
        )],
        vulnerabilities=[SimpleNamespace(
            cve_id=detail.advisory.cve_id,
            advisory_summary=detail.advisory.summary,
            advisory_severity=detail.advisory.severity,
            candidates=candidates,
        )],
    )
    monkeypatch.setattr(
        "watchback_backend.remediation.service.list_remediation_groups",
        lambda session, context: SimpleNamespace(items=[group]),
    )

    sources = ai_context.build_grounding_sources(
        object(), request_context, None, group_id
    )

    candidate_sources = [source for source in sources if source.source_type == "candidate"]
    assert len(candidate_sources) == 2
    assert all(detail.advisory.summary in source.content for source in candidate_sources)
    assert any("현재 버전=1.9.0" in source.content for source in sources)
    assert all(source.organization_id == organization_id for source in sources)


def test_litellm_context_adds_advisory_details_with_user_facing_source_titles(
    monkeypatch,
) -> None:
    organization_id = uuid4()
    request_context = RequestContext(organization_id, uuid4(), "검토자")
    detail = ReviewCaseDetail.model_validate(DETAIL_EXAMPLE)
    cve_id = "CVE-2026-42208"
    ghsa_id = "GHSA-r75f-5x8p-qvmc"
    candidate = detail.candidates[0].model_copy(
        update={
            "cve_id": cve_id,
            "ghsa_id": ghsa_id,
            "change_type": "epss_rise_d30",
        }
    )
    evidence = candidate.evidence[0].model_copy(
        update={"signal": "epss_score_d30", "source": "first_epss"}
    )
    candidate = candidate.model_copy(update={"evidence": [evidence]})
    alert = SimpleNamespace(
        **detail.alert.model_dump(),
        cve_id=cve_id,
        ghsa_id=ghsa_id,
    )
    group_id = "b" * 64
    group = SimpleNamespace(
        id=group_id,
        package_name="litellm",
        ecosystem="pip",
        priority="P0",
        cve_count=1,
        repository_count=1,
        github_alert_counts=SimpleNamespace(open=1),
        recommended_fix_versions=["1.83.7"],
        updated_at=detail.updated_at,
        targets=[
            SimpleNamespace(
                current_versions=["1.81.16"],
                repository=detail.repository,
                manifest_path=detail.alert.manifest_path,
                alerts=[alert],
            )
        ],
        vulnerabilities=[
            SimpleNamespace(
                cve_id=cve_id,
                ghsa_id=ghsa_id,
                advisory_summary="LiteLLM SQL Injection",
                advisory_severity="critical",
                candidates=[candidate],
            )
        ],
    )
    advisory = SimpleNamespace(
        cve_id=cve_id,
        ghsa_id=ghsa_id,
        severity="critical",
        summary="LiteLLM SQL Injection",
        description=(
            "An unauthenticated attacker can send a crafted Authorization header. "
            "Upgrade to 1.83.7 or set disable_error_logs as a workaround."
        ),
        github_updated_at=datetime(2026, 5, 12, tzinfo=UTC),
    )

    class FakeSession:
        def __init__(self):
            self.scalar_queries = 0

        def scalars(self, _statement):
            self.scalar_queries += 1
            rows = [advisory] if self.scalar_queries == 1 else []
            return SimpleNamespace(all=lambda: rows)

    monkeypatch.setattr(
        "watchback_backend.remediation.service.list_remediation_groups",
        lambda session, context: SimpleNamespace(items=[group]),
    )

    sources = ai_context.build_grounding_sources(
        FakeSession(), request_context, None, group_id
    )

    advisory_source = next(source for source in sources if source.source_type == "advisory")
    assert advisory_source.title == f"{cve_id} 취약점 원문"
    assert "unauthenticated attacker" in advisory_source.content
    assert advisory_source.source_url == f"https://github.com/advisories/{ghsa_id}"
    assert any("EPSS 악용 가능성 상승" in source.title for source in sources)
    assert all("epss_score_d30" not in source.title for source in sources)
    assert all("DS 우선순위" not in source.content for source in sources)
