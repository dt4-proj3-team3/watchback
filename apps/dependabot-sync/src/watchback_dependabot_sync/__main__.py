from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from uuid import uuid4

from .config import GITHUB_API_VERSION, Settings
from .errors import SyncError
from .service import run_sync


def main() -> int:
    run_id = str(uuid4())
    started_at = datetime.now(UTC)
    result: dict[str, object] = {
        "run_id": run_id,
        "started_at": started_at.isoformat(),
        "api_version": GITHUB_API_VERSION,
        "success": False,
        "db_applied": False,
    }
    exit_code = 1
    try:
        settings = Settings.from_environment()
        result.update(run_sync(settings))
        result["success"] = True
        exit_code = 0
    except SyncError as exc:
        result["error"] = {
            "code": exc.code,
            "message": str(exc),
            **exc.context,
        }
    except ValueError as exc:
        result["error"] = {"code": "configuration_error", "message": str(exc)}
    except Exception:
        result["error"] = {
            "code": "unexpected_error",
            "message": "예상하지 못한 오류가 발생했습니다.",
        }
    result["finished_at"] = datetime.now(UTC).isoformat()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True), flush=True)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
