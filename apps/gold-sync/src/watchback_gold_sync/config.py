from __future__ import annotations

import os
from dataclasses import dataclass, field


FABRIC_SCHEMA = "gold"
BATCH_VIEW = "publish_rereview_batch"
CANDIDATE_VIEW = "publish_rereview_candidate"
EVIDENCE_VIEW = "publish_rereview_candidate_evidence"


@dataclass(frozen=True)
class Settings:
    fabric_sql_server: str
    fabric_sql_database: str
    database_url: str
    fabric_sql_access_token: str | None = field(default=None, repr=False)

    @classmethod
    def from_environment(cls) -> "Settings":
        values = {
            "FABRIC_SQL_SERVER": os.environ.get("FABRIC_SQL_SERVER"),
            "FABRIC_SQL_DATABASE": os.environ.get("FABRIC_SQL_DATABASE"),
            "DATABASE_URL": os.environ.get("DATABASE_URL"),
        }
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise ValueError(f"필수 환경변수가 없습니다: {', '.join(missing)}")
        return cls(
            fabric_sql_server=values["FABRIC_SQL_SERVER"] or "",
            fabric_sql_database=values["FABRIC_SQL_DATABASE"] or "",
            database_url=values["DATABASE_URL"] or "",
            fabric_sql_access_token=os.environ.get("FABRIC_SQL_ACCESS_TOKEN"),
        )
