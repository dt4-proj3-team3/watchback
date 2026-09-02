from __future__ import annotations

import os
from dataclasses import dataclass


GITHUB_API_VERSION = "2022-11-28"
GITHUB_API_URL = "https://api.github.com"
ORGANIZATION_LOGIN = "dt4-proj3-team3"
ORGANIZATION_GITHUB_ID = 314105294
REPOSITORIES = {
    "dt4-proj3-team3/watchback-vulnerable-fe-lab": 1329314801,
    "dt4-proj3-team3/watchback-vulnerable-be-lab": 1340408606,
    "dt4-proj3-team3/watchback-vulnerable-admin-fe-lab": 1353650380,
    "dt4-proj3-team3/watchback-vulnerable-reporting-be-lab": 1353650477,
}


@dataclass(frozen=True)
class Settings:
    github_token: str
    database_url: str
    github_api_url: str = GITHUB_API_URL

    @classmethod
    def from_environment(cls) -> "Settings":
        github_token = os.environ.get("GITHUB_TOKEN")
        database_url = os.environ.get("DATABASE_URL")
        missing = [
            name
            for name, value in (
                ("GITHUB_TOKEN", github_token),
                ("DATABASE_URL", database_url),
            )
            if not value
        ]
        if missing:
            raise ValueError(f"필수 환경변수가 없습니다: {', '.join(missing)}")
        return cls(github_token=github_token, database_url=database_url)
