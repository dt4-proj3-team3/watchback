from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from watchback_backend.ai_agent.context import build_grounding_sources
from watchback_backend.ai_agent.remediation_summary_prompt import (
    PROMPT_VERSION,
    build_remediation_summary_prompt,
    normalize_summary_display_text,
    parse_remediation_summary,
    remove_leading_package_reference,
)
from watchback_backend.ai_agent.service import AgentRequest, AgentService
from watchback_backend.api.service import RequestContext
from watchback_backend.db.models import RemediationAISummary
from watchback_backend.remediation.schemas import RemediationAISummaryResponse
from watchback_backend.remediation.service import list_remediation_groups


def backfill_remediation_summaries(
    session: Session,
    context: RequestContext,
    agent: AgentService,
    *,
    now: datetime | None = None,
) -> list[RemediationAISummaryResponse]:
    generated_at = now or datetime.now(UTC)
    groups = list_remediation_groups(session, context).items
    existing = {
        item.group_key: item
        for item in session.scalars(
            select(RemediationAISummary).where(
                RemediationAISummary.organization_id == context.organization_id
            )
        ).all()
    }
    results: list[RemediationAISummaryResponse] = []
    for group in groups:
        sources = build_grounding_sources(
            session,
            context,
            case_id=None,
            remediation_group_id=group.id,
        )
        answer = agent.answer(
            AgentRequest(
                organization_id=context.organization_id,
                question=build_remediation_summary_prompt(group),
                sources=sources,
            )
        )
        parsed = parse_remediation_summary(answer.text)
        risk_summary = normalize_summary_display_text(
            remove_leading_package_reference(
                parsed.risk_summary,
                group.package_name,
            )
        )
        action_summary = normalize_summary_display_text(
            f"{group.representative_patched_version} 이상으로 업데이트한 뒤 "
            "애플리케이션 테스트를 수행하세요."
            if group.representative_patched_version
            else remove_leading_package_reference(
                parsed.action_summary,
                group.package_name,
            )
        )
        row = existing.get(group.id)
        if row is None:
            row = RemediationAISummary(
                id=uuid4(),
                organization_id=context.organization_id,
                group_key=group.id,
            )
            session.add(row)
        row.ecosystem = group.ecosystem
        row.package_name = group.package_name
        row.prompt_version = PROMPT_VERSION
        row.risk_summary = risk_summary
        row.action_summary = action_summary
        row.interpretation_note = (
            normalize_summary_display_text(parsed.interpretation_note)
            if parsed.interpretation_note
            else None
        )
        row.model = answer.model
        row.source_ids = list(answer.source_ids)
        row.generated_at = generated_at
        session.flush()
        results.append(RemediationAISummaryResponse.model_validate(row))
    session.commit()
    return results


def normalize_existing_summary_package_references(
    session: Session,
    context: RequestContext,
) -> int:
    rows = session.scalars(
        select(RemediationAISummary).where(
            RemediationAISummary.organization_id == context.organization_id
        )
    ).all()
    changed = 0
    for row in rows:
        risk_summary = normalize_summary_display_text(
            remove_leading_package_reference(
                row.risk_summary,
                row.package_name,
            )
        )
        action_summary = normalize_summary_display_text(
            remove_leading_package_reference(
                row.action_summary,
                row.package_name,
            )
        )
        interpretation_note = (
            normalize_summary_display_text(row.interpretation_note)
            if getattr(row, "interpretation_note", None)
            else None
        )
        if (
            risk_summary == row.risk_summary
            and action_summary == row.action_summary
            and interpretation_note == getattr(row, "interpretation_note", None)
        ):
            continue
        row.risk_summary = risk_summary
        row.action_summary = action_summary
        row.interpretation_note = interpretation_note
        changed += 1
    session.commit()
    return changed
