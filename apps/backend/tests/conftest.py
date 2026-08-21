from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, inspect
from testcontainers.community.postgres import PostgresContainer


@pytest.fixture(scope="session")
def postgres_engine() -> Engine:
    config = Config(Path(__file__).parents[1] / "alembic.ini")
    previous_database_url = os.environ.get("DATABASE_URL")

    with PostgresContainer("postgres:16-alpine", driver="psycopg") as postgres:
        database_url = postgres.get_connection_url()
        os.environ["DATABASE_URL"] = database_url
        command.upgrade(config, "head")
        engine = create_engine(database_url)

        try:
            yield engine
        finally:
            command.downgrade(config, "base")
            assert set(inspect(engine).get_table_names()) == {"alembic_version"}
            engine.dispose()
            if previous_database_url is None:
                os.environ.pop("DATABASE_URL", None)
            else:
                os.environ["DATABASE_URL"] = previous_database_url
