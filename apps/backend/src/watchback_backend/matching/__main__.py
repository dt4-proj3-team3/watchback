from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from uuid import UUID, uuid4

from .service import MatchingError, run_matching


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Gold 위험 후보와 조직의 Open Dependabot Alert를 매칭합니다."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="매칭 결과만 계산하고 DB에 저장하지 않습니다.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    started_at = datetime.now(UTC)
    output: dict[str, object] = {
        "run_id": str(uuid4()),
        "started_at": started_at.isoformat(),
        "success": False,
        "dry_run": args.dry_run,
        "db_applied": False,
    }
    exit_code = 1
    try:
        database_url = os.getenv("DATABASE_URL")
        organization_value = os.getenv("ORGANIZATION_ID")
        if not database_url:
            raise ValueError("DATABASE_URL 환경변수가 필요합니다.")
        if not organization_value:
            raise ValueError("ORGANIZATION_ID 환경변수가 필요합니다.")
        organization_id = UUID(organization_value)
        output.update(
            run_matching(
                database_url,
                organization_id,
                dry_run=args.dry_run,
            )
        )
        output["success"] = True
        exit_code = 0
    except MatchingError as exc:
        output["error"] = {
            "code": exc.code,
            "message": str(exc),
            **exc.context,
        }
    except ValueError as exc:
        output["error"] = {"code": "configuration_error", "message": str(exc)}
    except Exception:
        output["error"] = {
            "code": "unexpected_error",
            "message": "예상하지 못한 오류가 발생했습니다.",
        }
    output["finished_at"] = datetime.now(UTC).isoformat()
    print(json.dumps(output, ensure_ascii=False, sort_keys=True), flush=True)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
