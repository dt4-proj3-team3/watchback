from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol
from uuid import UUID


SourceType = Literal[
    "review_case",
    "candidate",
    "evidence",
    "advisory",
    "usage_analysis",
    "upgrade_analysis",
    "dependabot_alert",
    "review_activity",
    "source_annotation",
]


@dataclass(frozen=True)
class AgentMessage:
    role: Literal["user", "assistant"]
    content: str


@dataclass(frozen=True)
class GroundingSource:
    organization_id: UUID
    source_type: SourceType
    source_id: str
    title: str
    content: str
    observed_at: datetime
    source_url: str | None = None


@dataclass(frozen=True)
class AgentRequest:
    organization_id: UUID
    question: str
    sources: Sequence[GroundingSource]
    messages: Sequence[AgentMessage] = ()


@dataclass(frozen=True)
class AgentAnswer:
    text: str
    source_ids: tuple[str, ...]
    model: str


class ModelClient(Protocol):
    @property
    def model(self) -> str: ...

    def respond(self, *, instructions: str, input_text: str) -> str: ...


class OrganizationScopeError(ValueError):
    """요청 조직과 다른 조직의 근거가 포함된 경우 발생한다."""


class MissingGroundingError(ValueError):
    """답변을 뒷받침할 Watchback 근거가 없는 경우 발생한다."""


class AgentService:
    def __init__(self, client: ModelClient) -> None:
        self._client = client

    def answer(self, request: AgentRequest) -> AgentAnswer:
        from watchback_backend.ai_agent.prompt import (
            SYSTEM_INSTRUCTIONS,
            build_grounded_input,
        )

        if not request.sources:
            raise MissingGroundingError(
                "질문에 답할 수 있는 Watchback 근거가 없습니다."
            )

        foreign_sources = [
            source.source_id
            for source in request.sources
            if source.organization_id != request.organization_id
        ]
        if foreign_sources:
            raise OrganizationScopeError(
                "요청 조직과 다른 조직의 근거를 AI에 전달할 수 없습니다."
            )

        text = self._client.respond(
            instructions=SYSTEM_INSTRUCTIONS,
            input_text=build_grounded_input(
                request.question,
                request.sources,
                request.messages,
            ),
        )
        cited_indexes = {
            int(match)
            for match in re.findall(r"\[([1-9][0-9]*)\]", text)
            if int(match) <= len(request.sources)
        }
        return AgentAnswer(
            text=text,
            source_ids=tuple(
                source.source_id
                for index, source in enumerate(request.sources, 1)
                if index in cited_indexes
            ),
            model=self._client.model,
        )
