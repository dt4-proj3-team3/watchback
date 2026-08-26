from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from uuid import uuid4

from .config import Settings
from .errors import SyncError
from .service import run_sync


def main() -> int:
    result: dict[str, object] = {
        "run_id": str(uuid4()),
        "started_at": datetime.now(UTC).isoformat(),
        "success": False,
        "db_applied": False,
    }
    exit_code = 1
    try:
        sync = run_sync(Settings.from_environment())
        result.update(sync.payload)
        result["success"] = not sync.has_failures
        result["db_applied"] = any(
            item.get("db_applied") for item in sync.payload["batches"]
        )
        exit_code = 1 if sync.has_failures else 0
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
