from __future__ import annotations

import os
from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


def _database_url() -> str:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL 환경변수가 필요합니다.")
    return database_url


@lru_cache(maxsize=None)
def _engine(database_url: str) -> Engine:
    return create_engine(database_url, pool_pre_ping=True)


@lru_cache(maxsize=None)
def _session_factory(database_url: str) -> sessionmaker[Session]:
    return sessionmaker(
        bind=_engine(database_url),
        expire_on_commit=False,
        class_=Session,
    )


def get_session() -> Iterator[Session]:
    """요청 시점에만 DATABASE_URL을 읽고 DB Session을 생성한다."""

    with _session_factory(_database_url())() as session:
        yield session
