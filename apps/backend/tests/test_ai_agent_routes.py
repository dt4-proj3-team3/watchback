from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from watchback_backend.ai_agent.config import require_agent_service
from watchback_backend.ai_agent.routes import router
from watchback_backend.ai_agent.service import AgentAnswer, GroundingSource
from watchback_backend.api import service as api_service
from watchback_backend.db.session import get_session


ORGANIZATION_ID = uuid4()
USER_ID = uuid4()


class FakeAgent:
    def __init__(self) -> None:
        self.request = None

    def answer(self, request):
        self.request = request
        return AgentAnswer(
            text="KEV 등재를 근거로 다시 검토해야 합니다. [1]",
            source_ids=(request.sources[0].source_id,),
            model="gpt-5.6-luna",
        )


def _session() -> Iterator[object]:
    yield object()


def _client(monkeypatch, agent: FakeAgent, sources: list[GroundingSource]) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[require_agent_service] = lambda: agent
    monkeypatch.setattr(
        "watchback_backend.ai_agent.routes.require_context",
        lambda session, organization_id, user_id: api_service.RequestContext(
            organization_id, user_id, "검토자"
        ),
    )
    monkeypatch.setattr(
        "watchback_backend.ai_agent.routes.build_grounding_sources",
        lambda session, context, case_id, remediation_group_id: sources,
    )
    return TestClient(app)


def test_ai_review_route_returns_answer_and_grounding_sources(monkeypatch) -> None:
    agent = FakeAgent()
    case_id = uuid4()
    source = GroundingSource(
        organization_id=ORGANIZATION_ID,
        source_type="evidence",
        source_id="evidence:1",
        title="CISA KEV 등재",
        content="미등재에서 등재로 변경",
        observed_at=datetime(2026, 5, 8, tzinfo=UTC),
        source_url="https://www.cisa.gov/known-exploited-vulnerabilities-catalog",
    )
    client = _client(monkeypatch, agent, [source])

    response = client.post(
        "/api/v1/ai/review",
        headers={
            "X-Organization-ID": str(ORGANIZATION_ID),
            "X-User-ID": str(USER_ID),
        },
        json={
            "question": "왜 다시 검토해야 하나요?",
            "case_id": str(case_id),
            "history": [{"role": "user", "content": "이 Case를 보고 있어"}],
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "answer": "KEV 등재를 근거로 다시 검토해야 합니다. [1]",
        "model": "gpt-5.6-luna",
        "sources": [
            {
                "citation": "1",
                "source_id": "evidence:1",
                "source_type": "evidence",
                "title": "CISA KEV 등재",
                "observed_at": "2026-05-08T00:00:00Z",
                "source_url": "https://www.cisa.gov/known-exploited-vulnerabilities-catalog",
            }
        ],
    }
    assert agent.request.organization_id == ORGANIZATION_ID
    assert agent.request.question == "왜 다시 검토해야 하나요?"
    assert agent.request.messages[0].content == "이 Case를 보고 있어"


def test_ai_review_route_returns_curated_group_answer_without_model_call(
    monkeypatch,
) -> None:
    agent = FakeAgent()
    source = GroundingSource(
        organization_id=ORGANIZATION_ID,
        source_type="review_case",
        source_id="remediation_group:1",
        title="litellm 패키지 조치 후보",
        content="저장소=2곳",
        observed_at=datetime(2026, 9, 2, tzinfo=UTC),
    )
    monkeypatch.setattr(
        "watchback_backend.ai_agent.routes.find_curated_answer",
        lambda session, organization_id, group_key, question, sources: AgentAnswer(
            text="저장된 답변입니다. [1]",
            source_ids=(sources[0].source_id,),
            model="watchback-curated-v1",
        ),
    )
    client = _client(monkeypatch, agent, [source])

    response = client.post(
        "/api/v1/ai/review",
        headers={
            "X-Organization-ID": str(ORGANIZATION_ID),
            "X-User-ID": str(USER_ID),
        },
        json={
            "question": "이 업데이트로 어떤 문제가 해결되나요?",
            "remediation_group_id": "a" * 64,
        },
    )

    assert response.status_code == 200
    assert response.json()["answer"] == "저장된 답변입니다. [1]"
    assert response.json()["model"] == "watchback-curated-v1"
    assert response.json()["sources"][0]["citation"] == "1"
    assert agent.request is None


def test_ai_review_route_limits_question_and_session_history(monkeypatch) -> None:
    client = _client(monkeypatch, FakeAgent(), [])
    headers = {
        "X-Organization-ID": str(ORGANIZATION_ID),
        "X-User-ID": str(USER_ID),
    }

    long_question = client.post(
        "/api/v1/ai/review",
        headers=headers,
        json={"question": "가" * 1001},
    )
    long_history = client.post(
        "/api/v1/ai/review",
        headers=headers,
        json={
            "question": "요약해줘",
            "history": [
                {"role": "user", "content": "가" * 501}
                for _ in range(8)
            ],
        },
    )

    assert long_question.status_code == 422
    assert long_history.status_code == 422
