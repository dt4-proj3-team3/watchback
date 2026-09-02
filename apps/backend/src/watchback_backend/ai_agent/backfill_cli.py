from __future__ import annotations

import argparse
from uuid import UUID

from watchback_backend.ai_agent.config import get_agent_service
from watchback_backend.ai_agent.remediation_summary import (
    backfill_remediation_summaries,
    normalize_existing_summary_package_references,
)
from watchback_backend.ai_agent.remediation_summary_prompt import PROMPT_VERSION
from watchback_backend.api.service import require_context
from watchback_backend.db.session import get_session


def main() -> None:
    parser = argparse.ArgumentParser(
        description="현재 패키지 조치 그룹의 AI 요약을 일괄 생성해 DB에 저장합니다."
    )
    parser.add_argument("--organization-id", type=UUID, required=True)
    parser.add_argument("--user-id", type=UUID, required=True)
    parser.add_argument(
        "--normalize-existing",
        action="store_true",
        help=(
            "LLM 호출 없이 기존 저장 요약의 패키지명, 날짜, "
            "EPSS 백분율 표기를 정규화합니다."
        ),
    )
    args = parser.parse_args()

    sessions = get_session()
    session = next(sessions)
    try:
        context = require_context(session, args.organization_id, args.user_id)
        if args.normalize_existing:
            changed = normalize_existing_summary_package_references(
                session,
                context,
            )
            print(f"normalized={changed}")
            return
        summaries = backfill_remediation_summaries(
            session, context, get_agent_service()
        )
    finally:
        sessions.close()
    print(f"stored={len(summaries)} prompt_version={PROMPT_VERSION}")


if __name__ == "__main__":
    main()
