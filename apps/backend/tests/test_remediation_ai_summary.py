from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

import pytest

from watchback_backend.ai_agent.remediation_summary import (
    backfill_remediation_summaries,
    normalize_existing_summary_package_references,
)
from watchback_backend.ai_agent.remediation_summary_prompt import (
    PROMPT_VERSION,
    REMEDIATION_SUMMARY_PROMPT,
    build_remediation_summary_prompt,
    normalize_summary_display_text,
    parse_remediation_summary,
    remove_leading_package_reference,
)
from watchback_backend.ai_agent.service import AgentAnswer, GroundingSource
from watchback_backend.api.service import RequestContext


ORGANIZATION_ID = UUID("10000000-0000-0000-0000-000000000001")
USER_ID = UUID("20000000-0000-0000-0000-000000000001")
NOW = datetime(2026, 9, 1, tzinfo=UTC)


class _ScalarResult:
    def __init__(self, values):
        self._values = values

    def all(self):
        return self._values


class FakeSession:
    def __init__(self):
        self.rows = []
        self.commits = 0

    def scalars(self, statement):
        del statement
        return _ScalarResult(self.rows)

    def add(self, row):
        self.rows.append(row)

    def flush(self):
        pass

    def commit(self):
        self.commits += 1


class FakeAgent:
    def __init__(self):
        self.questions = []

    def answer(self, request):
        self.questions.append(request.question)
        return AgentAnswer(
            text=(
                "핵심 위험: litellm의 SQL Injection 취약점이 5월 8일 CISA KEV에 "
                "새로 등재되었고 실제 악용 사례가 확인되었습니다. [S1]\n"
                "권장 조치: litellm 패키지를 1.83.10 이상으로 업데이트한 뒤 애플리케이션 "
                "테스트를 수행하세요. [S2]"
            ),
            source_ids=("evidence:1", "dependabot_alert:1"),
            model="gpt-5.6-luna",
        )


def test_versioned_prompt_requires_user_facing_epss_values() -> None:
    assert PROMPT_VERSION == "remediation-summary-v7"
    assert "향후 30일 악용 가능성이 이전 N%에서 현재 N%" in REMEDIATION_SUMMARY_PROMPT
    assert "전체 CVE 중 상위 N%" in REMEDIATION_SUMMARY_PROMPT
    assert "DS, P0, P1, P2, P3" in REMEDIATION_SUMMARY_PROMPT
    assert "패키지명은 화면 상단에 있으므로" in REMEDIATION_SUMMARY_PROMPT
    assert "해석 주의: <한 문장 또는 없음>" in REMEDIATION_SUMMARY_PROMPT
    assert "CISA를 판단 주체로" in REMEDIATION_SUMMARY_PROMPT


def test_summary_parser_removes_citations_and_rejects_internal_terms() -> None:
    parsed = parse_remediation_summary(
        "핵심 위험: 5월 8일 실제 악용 사례가 확인되었습니다. [S1]\n"
        "권장 조치: 1.83.10 이상으로 업데이트한 뒤 테스트하세요. [S2]"
    )
    assert parsed.risk_summary == "5월 8일 실제 악용 사례가 확인되었습니다."
    assert parsed.action_summary == "1.83.10 이상으로 업데이트한 뒤 테스트하세요."
    assert parsed.interpretation_note is None

    with pytest.raises(ValueError, match="내부 용어"):
        parse_remediation_summary(
            "핵심 위험: DS P0 후보입니다. [S1]\n"
            "권장 조치: 테스트하세요. [S2]"
        )


def test_backfill_generates_every_group_and_persists_rows(monkeypatch) -> None:
    groups = [
        SimpleNamespace(id="a" * 64, ecosystem="pip", package_name="litellm", representative_patched_version="1.83.10", vulnerabilities=[]),
        SimpleNamespace(id="b" * 64, ecosystem="npm", package_name="vite", representative_patched_version="6.4.2", vulnerabilities=[]),
    ]
    source = GroundingSource(
        organization_id=ORGANIZATION_ID,
        source_type="evidence",
        source_id="evidence:1",
        title="CISA KEV 등재",
        content="미등재에서 등재로 변경",
        observed_at=NOW,
    )
    monkeypatch.setattr(
        "watchback_backend.ai_agent.remediation_summary.list_remediation_groups",
        lambda session, context: SimpleNamespace(items=groups),
    )
    monkeypatch.setattr(
        "watchback_backend.ai_agent.remediation_summary.build_grounding_sources",
        lambda session, context, case_id, remediation_group_id: [source],
    )
    session = FakeSession()
    agent = FakeAgent()

    results = backfill_remediation_summaries(
        session,
        RequestContext(ORGANIZATION_ID, USER_ID, "검토자"),
        agent,
        now=NOW,
    )

    assert len(results) == 2
    assert len(session.rows) == 2
    assert session.commits == 1
    assert all(question.startswith(REMEDIATION_SUMMARY_PROMPT) for question in agent.questions)
    assert {row.group_key for row in session.rows} == {"a" * 64, "b" * 64}
    assert all(row.prompt_version == PROMPT_VERSION for row in session.rows)
    assert session.rows[0].risk_summary.startswith("SQL Injection 취약점이")
    assert session.rows[0].action_summary == (
        "1.83.10 이상으로 업데이트한 뒤 애플리케이션 테스트를 수행하세요."
    )


def test_prompt_builder_formats_verified_evidence_dates_and_values() -> None:
    evidence = SimpleNamespace(
        id="evidence-1",
        signal="epss_percentile_d30",
        previous_value="0.757",
        current_value="0.982",
        observed_at=datetime(2026, 6, 15, tzinfo=UTC),
    )
    group = SimpleNamespace(
        package_name="vite",
        representative_patched_version="6.4.2",
        vulnerabilities=[SimpleNamespace(
            cve_id="CVE-2026-0001",
            priority="P1",
            change_type="epss_top5_entry_d30",
            advisory_summary="Vite arbitrary file read",
            candidates=[SimpleNamespace(
                id="candidate-1",
                priority="P1",
                change_type="epss_top5_entry_d30",
                selected_at=datetime(2026, 6, 16, tzinfo=UTC),
                evidence=[evidence],
                deliveries=[SimpleNamespace(source_annotations=[SimpleNamespace(
                    snapshot_date=datetime(2026, 6, 15, tzinfo=UTC).date(),
                    label="EPSS 모델 v5 전환일",
                    description="모델 변경 영향이 함께 반영됐을 수 있습니다.",
                )])],
            )],
        )],
    )

    prompt = build_remediation_summary_prompt(group)

    assert "Evidence 관찰일 6월 15일" in prompt
    assert "전체 CVE 내 EPSS 순위 상위 24.3% → 상위 1.8%" in prompt
    assert "EPSS 모델·소스 변동 주석 6월 15일" in prompt


@pytest.mark.parametrize(
    ("text", "package_name", "expected"),
    [
        ("litellm에서 SQL 인젝션이 확인되었습니다.", "litellm", "SQL 인젝션이 확인되었습니다."),
        ("react-server-dom-webpack의 원격 코드 실행 취약점입니다.", "react-server-dom-webpack", "원격 코드 실행 취약점입니다."),
        ("Django 4.2.20에서 서비스 거부가 가능합니다.", "django", "서비스 거부가 가능합니다."),
        ("vite는 파일 접근 제한을 우회할 수 있습니다.", "vite", "파일 접근 제한을 우회할 수 있습니다."),
        ("vite 패키지를 6.4.2 이상으로 업데이트하세요.", "vite", "6.4.2 이상으로 업데이트하세요."),
    ],
)
def test_removes_only_leading_package_reference(
    text: str,
    package_name: str,
    expected: str,
) -> None:
    assert remove_leading_package_reference(text, package_name) == expected


def test_normalizes_existing_rows_without_changing_prompt_version() -> None:
    row = SimpleNamespace(
        package_name="vite",
        risk_summary=(
            "vite는 2026년 6월 15일 향후 30일 악용 가능성이 "
            "0.165%로 상승했습니다."
        ),
        action_summary="vite 패키지를 6.4.2 이상으로 업데이트하세요.",
        prompt_version="remediation-summary-v3",
        interpretation_note=None,
    )
    session = FakeSession()
    session.rows = [row]

    changed = normalize_existing_summary_package_references(
        session,
        RequestContext(ORGANIZATION_ID, USER_ID, "검토자"),
    )

    assert changed == 1
    assert row.risk_summary == (
        "6월 15일 향후 30일 악용 가능성이 0.17%로 상승했습니다."
    )
    assert row.action_summary == "6.4.2 이상으로 업데이트하세요."
    assert row.prompt_version == "remediation-summary-v3"
    assert session.commits == 1


def test_normalizes_summary_date_and_epss_precision() -> None:
    assert normalize_summary_display_text(
        "2026년 6월 15일 EPSS가 0.165%에서 7.1234%로 상승했습니다."
    ) == "6월 15일 EPSS가 0.17%에서 7.12%로 상승했습니다."
    assert normalize_summary_display_text(
        "실제 악용 사례가 확인되었다는 의미입니다."
    ) == "실제 악용 사례가 확인되었습니다."
    assert normalize_summary_display_text(
        "SQL 삽입 취약점으로, 5월 8일 CISA KEV에 새로 등재되어 실제 악용 "
        "사례가 확인되었다는 의미지만 Watchback 근거만으로 실제 악용 여부를 "
        "확정할 수 없습니다."
    ) == (
        "SQL 삽입 취약점으로, 5월 8일 CISA가 실제 악용이 확인된 취약점으로 "
        "KEV에 새로 등재했습니다."
    )


def test_removes_repeated_package_exploitation_disclaimer() -> None:
    assert remove_leading_package_reference(
        "SQL 삽입 취약점입니다. litellm에  확인되었다는 의미지만 Watchback "
        "근거만으로 실제 악용 여부를 확정할 수 없습니다.",
        "litellm",
    ) == "SQL 삽입 취약점입니다."


def test_parser_reads_interpretation_note() -> None:
    parsed = parse_remediation_summary(
        "핵심 위험: 서비스 거부 위험이 상승했습니다. [S1]\n"
        "권장 조치: 4.2.28 이상으로 업데이트하세요. [S2]\n"
        "해석 주의: 6월 15일 EPSS 모델·소스 변동과 겹쳐 소스 변동 영향이 "
        "함께 반영됐을 수 있습니다. [S3]"
    )

    assert parsed.interpretation_note == (
        "6월 15일 EPSS 모델·소스 변동과 겹쳐 소스 변동 영향이 "
        "함께 반영됐을 수 있습니다."
    )
