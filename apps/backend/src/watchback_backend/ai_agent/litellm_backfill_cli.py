from __future__ import annotations

import argparse
import os
from uuid import UUID

from watchback_backend.ai_agent.litellm_context import backfill_litellm_context
from watchback_backend.api.service import require_context
from watchback_backend.db.session import get_session


def main() -> None:
    parser = argparse.ArgumentParser(
        description="LiteLLM 저장소 단서와 업데이트 정보를 Web DB에 저장합니다."
    )
    parser.add_argument("--organization-id", type=UUID, required=True)
    parser.add_argument("--user-id", type=UUID, required=True)
    args = parser.parse_args()
    github_token = os.getenv("GITHUB_REMEDIATION_TOKEN")
    if not github_token:
        raise RuntimeError("GITHUB_REMEDIATION_TOKEN 환경변수가 필요합니다.")

    sessions = get_session()
    session = next(sessions)
    try:
        context = require_context(session, args.organization_id, args.user_id)
        documents = backfill_litellm_context(session, context, github_token)
    finally:
        sessions.close()
    print(f"stored={len(documents)} package=litellm")


if __name__ == "__main__":
    main()
