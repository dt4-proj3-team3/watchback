from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from watchback_backend.ai_agent.azure_openai import AzureOpenAIRequestError
from watchback_backend.ai_agent.config import require_agent_service
from watchback_backend.ai_agent.context import build_grounding_sources
from watchback_backend.ai_agent.curated import find_curated_answer
from watchback_backend.ai_agent.schemas import (
    AIReviewRequest,
    AIReviewResponse,
    AISourceResponse,
)
from watchback_backend.ai_agent.service import (
    AgentMessage,
    AgentRequest,
    AgentService,
    MissingGroundingError,
)
from watchback_backend.api.routes import ContextHeaders, get_context_headers
from watchback_backend.api.service import ServiceError, require_context
from watchback_backend.db.session import get_session


router = APIRouter(prefix="/api/v1/ai", tags=["ai-review-assistant"])


@router.post(
    "/review",
    response_model=AIReviewResponse,
    summary="근거 기반 재검토 설명",
)
def review_with_ai(
    payload: AIReviewRequest,
    headers: Annotated[ContextHeaders, Depends(get_context_headers)],
    session: Annotated[Session, Depends(get_session)],
    agent: Annotated[AgentService, Depends(require_agent_service)],
) -> AIReviewResponse:
    context = require_context(session, headers.organization_id, headers.user_id)
    sources = build_grounding_sources(
        session,
        context,
        payload.case_id,
        payload.remediation_group_id,
    )
    answer = (
        find_curated_answer(
            session,
            context.organization_id,
            payload.remediation_group_id,
            payload.question,
            sources,
        )
        if payload.remediation_group_id is not None
        else None
    )
    try:
        answer = answer or agent.answer(
            AgentRequest(
                organization_id=context.organization_id,
                question=payload.question,
                sources=sources,
                messages=[
                    AgentMessage(role=message.role, content=message.content)
                    for message in payload.history
                ],
            )
        )
    except MissingGroundingError as exc:
        raise ServiceError(404, "ai_grounding_not_found", str(exc)) from exc
    except AzureOpenAIRequestError as exc:
        raise ServiceError(
            502,
            "ai_backend_unavailable",
            "AI 검토 도우미에 일시적으로 연결할 수 없습니다.",
        ) from exc

    source_by_id = {source.source_id: source for source in sources}
    citation_by_id = {
        source.source_id: str(index) for index, source in enumerate(sources, 1)
    }
    return AIReviewResponse(
        answer=answer.text,
        model=answer.model,
        sources=[
            AISourceResponse(
                citation=citation_by_id[source_id],
                source_id=source.source_id,
                source_type=source.source_type,
                title=source.title,
                observed_at=source.observed_at,
                source_url=source.source_url,
            )
            for source_id in answer.source_ids
            if (source := source_by_id.get(source_id)) is not None
        ],
    )
