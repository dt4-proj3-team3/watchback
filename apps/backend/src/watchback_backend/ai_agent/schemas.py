from __future__ import annotations

from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from watchback_backend.ai_agent.service import SourceType


class AIContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class AIHistoryMessage(AIContractModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=1000)


class AIReviewRequest(AIContractModel):
    question: str = Field(min_length=1, max_length=1000)
    case_id: UUID | None = None
    remediation_group_id: str | None = Field(
        default=None, min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$"
    )
    history: list[AIHistoryMessage] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def validate_history_size(self) -> Self:
        if self.case_id is not None and self.remediation_group_id is not None:
            raise ValueError("case_id와 remediation_group_id는 동시에 지정할 수 없습니다.")
        if sum(len(message.content) for message in self.history) > 4000:
            raise ValueError("대화 이력은 합계 4,000자 이하여야 합니다.")
        return self


class AISourceResponse(AIContractModel):
    citation: str = Field(pattern=r"^[1-9][0-9]*$")
    source_id: str
    source_type: SourceType
    title: str
    observed_at: datetime
    source_url: HttpUrl | None = None


class AIReviewResponse(AIContractModel):
    answer: str
    model: str
    sources: list[AISourceResponse]
