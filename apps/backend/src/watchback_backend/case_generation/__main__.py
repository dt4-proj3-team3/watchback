from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from uuid import UUID, uuid4

from .service import CaseGenerationError, run_case_generation


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="조직의 Open Alert–Candidate 매칭 결과를 재검토 Case로 만듭니다."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Case 생성 결과만 계산하고 DB를 변경하지 않습니다.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    output: dict[str, object] = {
        "run_id": str(uuid4()),
        "started_at": datetime.now(UTC).isoformat(),
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
        output.update(
            run_case_generation(
                database_url,
                UUID(organization_value),
                dry_run=args.dry_run,
            )
        )
        output["success"] = True
        exit_code = 0
    except CaseGenerationError as exc:
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
