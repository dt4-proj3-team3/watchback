from __future__ import annotations

import re
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from watchback_backend.ai_agent.service import AgentAnswer, GroundingSource
from watchback_backend.db.models import AIContextDocument


CURATED_MODEL = "watchback-curated-v1"


def find_curated_answer(
    session: Session,
    organization_id: UUID,
    group_key: str,
    question: str,
    sources: list[GroundingSource],
) -> AgentAnswer | None:
    document = session.scalar(
        select(AIContextDocument).where(
            AIContextDocument.organization_id == organization_id,
            AIContextDocument.group_key == group_key,
            AIContextDocument.document_type == "upgrade_notes",
        )
    )
    if document is None:
        return None
    text = document.content.get("curated_answers", {}).get(question.strip())
    if not text:
        return None
    cited_indexes = {
        int(value)
        for value in re.findall(r"\[([1-9][0-9]*)\]", text)
        if int(value) <= len(sources)
    }
    return AgentAnswer(
        text=text,
        source_ids=tuple(
            source.source_id
            for index, source in enumerate(sources, 1)
            if index in cited_indexes
        ),
        model=CURATED_MODEL,
    )
