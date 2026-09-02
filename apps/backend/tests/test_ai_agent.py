from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from watchback_backend.ai_agent.prompt import SYSTEM_INSTRUCTIONS
from watchback_backend.ai_agent.service import (
    AgentMessage,
    AgentRequest,
    AgentService,
    GroundingSource,
    MissingGroundingError,
    OrganizationScopeError,
)


class FakeModelClient:
    model = "gpt-5.6-luna"

    def __init__(self) -> None:
        self.instructions = ""
        self.input_text = ""

    def respond(self, *, instructions: str, input_text: str) -> str:
        self.instructions = instructions
        self.input_text = input_text
        return "EPSS 변화 때문에 다시 선정되었습니다. [1]"


def make_source(organization_id, *, source_id="evidence-1") -> GroundingSource:
    return GroundingSource(
        organization_id=organization_id,
        source_type="evidence",
        source_id=source_id,
        title="EPSS 급등",
        content="EPSS 점수가 0.08%에서 56.9%로 상승했습니다.",
        observed_at=datetime(2026, 6, 15, 9, 0, tzinfo=UTC),
        source_url="https://www.first.org/epss/data",
    )


def test_agent_uses_only_scoped_grounding_and_returns_source_ids() -> None:
    organization_id = uuid4()
    client = FakeModelClient()
    service = AgentService(client)

    answer = service.answer(
        AgentRequest(
            organization_id=organization_id,
            question="왜 다시 검토해야 하나요?",
            sources=[make_source(organization_id)],
            messages=[AgentMessage(role="user", content="이 Case를 요약해줘")],
        )
    )

    assert answer.model == "gpt-5.6-luna"
    assert answer.source_ids == ("evidence-1",)
    assert "[1]" in answer.text
    assert "실제 악용 여부" in client.instructions
    assert "P0, P1, P2, P3" in client.instructions
    assert client.instructions == SYSTEM_INSTRUCTIONS
    assert "관찰 시각(UTC): 2026-06-15T09:00:00+00:00" in client.input_text
    assert "EPSS 점수가 0.08%에서 56.9%로 상승했습니다." in client.input_text
    assert "이 Case를 요약해줘" in client.input_text
    assert "식별자:" not in client.input_text


def test_agent_returns_only_sources_explicitly_cited_by_the_model() -> None:
    organization_id = uuid4()
    client = FakeModelClient()
    service = AgentService(client)

    answer = service.answer(
        AgentRequest(
            organization_id=organization_id,
            question="핵심 근거만 알려줘",
            sources=[
                make_source(organization_id, source_id="evidence-1"),
                make_source(organization_id, source_id="evidence-2"),
            ],
        )
    )

    assert answer.source_ids == ("evidence-1",)


def test_agent_rejects_foreign_organization_source_before_model_call() -> None:
    client = FakeModelClient()
    service = AgentService(client)

    with pytest.raises(OrganizationScopeError):
        service.answer(
            AgentRequest(
                organization_id=uuid4(),
                question="요약해줘",
                sources=[make_source(uuid4())],
            )
        )

    assert client.input_text == ""


def test_agent_rejects_request_without_grounding_before_model_call() -> None:
    client = FakeModelClient()

    with pytest.raises(MissingGroundingError):
        AgentService(client).answer(
            AgentRequest(
                organization_id=uuid4(),
                question="일반적인 취약점 설명을 해줘",
                sources=[],
            )
        )

    assert client.input_text == ""


def test_agent_omits_unsafe_source_url_from_model_input() -> None:
    organization_id = uuid4()
    client = FakeModelClient()
    source = make_source(organization_id)
    unsafe_source = GroundingSource(
        organization_id=source.organization_id,
        source_type=source.source_type,
        source_id=source.source_id,
        title=source.title,
        content=source.content,
        observed_at=source.observed_at,
        source_url="javascript:alert(1)",
    )

    AgentService(client).answer(
        AgentRequest(
            organization_id=organization_id,
            question="요약해줘",
            sources=[unsafe_source],
        )
    )

    assert "javascript:" not in client.input_text
