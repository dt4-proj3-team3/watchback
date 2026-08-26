from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from testcontainers.community.postgres import PostgresContainer


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    backend_root = Path(__file__).resolve().parents[2] / "backend"
    config = Config(backend_root / "alembic.ini")
    config.set_main_option("script_location", str(backend_root / "alembic"))
    config.set_main_option("prepend_sys_path", str(backend_root / "src"))
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
