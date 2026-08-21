from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from testcontainers.community.postgres import PostgresContainer

APP_ROOT = Path(__file__).parents[1]
REPO_ROOT = APP_ROOT.parents[1]
BACKEND_ROOT = REPO_ROOT / "apps" / "backend"
sys.path.insert(0, str(APP_ROOT / "src"))
sys.path.insert(0, str(BACKEND_ROOT / "src"))

from watchback_backend.db.demo_seed import seed_database


@pytest.fixture
def raw_alerts() -> list[dict[str, object]]:
    fixture = Path(__file__).parent / "fixtures" / "representative_alerts.json"
    return json.loads(fixture.read_text())


@pytest.fixture(scope="session")
def postgres_database_url():
    config = Config(BACKEND_ROOT / "alembic.ini")
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    previous = os.environ.get("DATABASE_URL")
    with PostgresContainer("postgres:16-alpine", driver="psycopg") as postgres:
        url = postgres.get_connection_url()
        os.environ["DATABASE_URL"] = url
        command.upgrade(config, "head")
        try:
            yield url
        finally:
            command.downgrade(config, "base")
            if previous is None:
                os.environ.pop("DATABASE_URL", None)
            else:
                os.environ["DATABASE_URL"] = previous


@pytest.fixture
def seeded_database_url(postgres_database_url):
    engine = create_engine(postgres_database_url)
    with engine.begin() as connection:
        tables = [
            row[0]
            for row in connection.execute(
                text(
                    "SELECT tablename FROM pg_tables "
                    "WHERE schemaname = 'public' AND tablename <> 'alembic_version'"
                )
            )
        ]
        if tables:
            quoted = ", ".join(f'"{name}"' for name in tables)
            connection.execute(text(f"TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE"))
    seed_database(engine)
    engine.dispose()
    return postgres_database_url
