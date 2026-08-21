from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import Engine, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from watchback_backend.db.demo_seed import (
    ORGANIZATION,
    REFERENCE_DATA_AS_OF,
    REPOSITORIES,
    USERS,
    SeedConflictError,
    database_url_from_environment,
    seed_demo_reference_data,
)
from watchback_backend.db.models import (
    Base,
    CandidateEvidence,
    DependabotAlert,
    GoldBatch,
    Organization,
    Repository,
    ReviewCase,
    RiskCandidate,
    SecurityAdvisory,
    User,
)


@pytest.fixture()
def clean_database(postgres_engine: Engine) -> Engine:
    table_names = ", ".join(f'"{table.name}"' for table in Base.metadata.sorted_tables)
    statement = text(f"TRUNCATE TABLE {table_names} CASCADE")
    with postgres_engine.begin() as connection:
        connection.execute(statement)
    try:
        yield postgres_engine
    finally:
        with postgres_engine.begin() as connection:
            connection.execute(statement)


def test_seed_creates_only_demo_reference_data(clean_database: Engine) -> None:
    with Session(clean_database) as session:
        result = seed_demo_reference_data(session)

        organization = session.scalar(select(Organization))
        users = list(session.scalars(select(User).order_by(User.email)))
        repositories = list(
            session.scalars(select(Repository).order_by(Repository.github_repository_id))
        )

        assert result.organization.created == 1
        assert result.users.created == 2
        assert result.repositories.created == 2
        assert organization is not None
        assert organization.id == ORGANIZATION["id"]
        assert organization.github_organization_id == 314105294
        assert organization.github_login == "dt4-proj3-team3"
        assert organization.display_name == "노바링크"

        assert [(user.email, user.display_name, user.github_user_id, user.is_demo) for user in users] == [
            ("junho.park@novalink.example", "박준호", None, True),
            ("seoyeon.kim@novalink.example", "김서연", None, True),
        ]
        assert [user.id for user in users] == [
            next(item["id"] for item in USERS if item["email"] == users[0].email),
            next(item["id"] for item in USERS if item["email"] == users[1].email),
        ]

        assert [
            (
                repository.id,
                repository.github_repository_id,
                repository.full_name,
                repository.display_name,
                repository.default_branch,
                repository.importance,
                repository.github_updated_at,
                repository.last_synced_at,
            )
            for repository in repositories
        ] == [
            (
                REPOSITORIES[0]["id"],
                1329314801,
                "dt4-proj3-team3/watchback-vulnerable-fe-lab",
                "novalink/customer-fe",
                "main",
                "critical",
                REPOSITORIES[0]["github_updated_at"],
                REFERENCE_DATA_AS_OF,
            ),
            (
                REPOSITORIES[1]["id"],
                1340408606,
                "dt4-proj3-team3/watchback-vulnerable-be-lab",
                "novalink/identity-api",
                "main",
                "high",
                REPOSITORIES[1]["github_updated_at"],
                REFERENCE_DATA_AS_OF,
            ),
        ]

        for model in (
            SecurityAdvisory,
            DependabotAlert,
            GoldBatch,
            RiskCandidate,
            CandidateEvidence,
            ReviewCase,
        ):
            assert session.scalar(select(func.count()).select_from(model)) == 0


def test_seed_is_idempotent_and_preserves_sync_owned_repository_fields(
    clean_database: Engine,
) -> None:
    with Session(clean_database) as session:
        first = seed_demo_reference_data(session)
        second = seed_demo_reference_data(session)

        assert second.organization.unchanged == 1
        assert second.users.unchanged == 2
        assert second.repositories.unchanged == 2
        assert second.organization_id == first.organization_id
        assert second.user_ids == first.user_ids
        assert second.repository_ids == first.repository_ids

        organization = session.get(Organization, first.organization_id)
        user = session.get(User, first.user_ids["seoyeon.kim@novalink.example"])
        repository = session.get(
            Repository,
            first.repository_ids["dt4-proj3-team3/watchback-vulnerable-fe-lab"],
        )
        assert organization is not None
        assert user is not None
        assert repository is not None

        organization.display_name = "잘못된 조직명"
        user.display_name = "잘못된 이름"
        user.github_user_id = 1234
        user.is_demo = False
        repository.importance = "low"
        repository.display_name = "잘못된 저장소 이름"
        repository.full_name = "dt4-proj3-team3/watchback-vulnerable-fe-lab-renamed"
        repository.default_branch = "develop"
        repository.github_updated_at = REFERENCE_DATA_AS_OF + timedelta(days=1)
        repository.last_synced_at = REFERENCE_DATA_AS_OF + timedelta(days=1)
        session.commit()

        repaired = seed_demo_reference_data(session)

        assert repaired.organization.updated == 1
        assert repaired.users.updated == 1
        assert repaired.users.unchanged == 1
        assert repaired.repositories.updated == 1
        assert repaired.repositories.unchanged == 1
        assert organization.display_name == "노바링크"
        assert (user.display_name, user.github_user_id, user.is_demo) == ("김서연", None, True)
        assert repository.importance == "critical"
        assert repository.display_name == "novalink/customer-fe"
        assert repository.full_name.endswith("-renamed")
        assert repository.default_branch == "develop"
        assert repository.github_updated_at == REFERENCE_DATA_AS_OF + timedelta(days=1)
        assert repository.last_synced_at == REFERENCE_DATA_AS_OF + timedelta(days=1)


def test_seed_rolls_back_all_changes_on_source_identity_conflict(
    clean_database: Engine,
) -> None:
    other_organization_id = uuid4()
    with Session(clean_database) as session:
        session.add_all(
            [
                Organization(
                    id=ORGANIZATION["id"],
                    github_organization_id=ORGANIZATION["github_organization_id"],
                    github_login=ORGANIZATION["github_login"],
                    display_name="변경 전 조직명",
                ),
                Organization(
                    id=other_organization_id,
                    github_organization_id=999999999,
                    github_login="another-org",
                    display_name="다른 조직",
                ),
                Repository(
                    id=uuid4(),
                    organization_id=other_organization_id,
                    github_repository_id=999999998,
                    full_name=REPOSITORIES[0]["full_name"],
                    display_name="another-org/customer-fe",
                    default_branch="main",
                    importance="low",
                    github_updated_at=REFERENCE_DATA_AS_OF,
                    last_synced_at=REFERENCE_DATA_AS_OF,
                ),
            ]
        )
        session.commit()

        with pytest.raises(SeedConflictError):
            seed_demo_reference_data(session)

        session.expire_all()
        organization = session.get(Organization, ORGANIZATION["id"])
        assert organization is not None
        assert organization.display_name == "변경 전 조직명"
        assert session.scalar(select(func.count()).select_from(User)) == 0
        assert session.scalar(select(func.count()).select_from(Repository)) == 1


@pytest.mark.parametrize("model", [User, Repository])
def test_organization_owned_reference_data_rejects_unknown_organization(
    clean_database: Engine, model: type[User] | type[Repository]
) -> None:
    with Session(clean_database) as session, pytest.raises(IntegrityError):
        if model is User:
            session.add(
                User(
                    organization_id=uuid4(),
                    email="unknown@example.com",
                    display_name="미등록 사용자",
                    is_demo=True,
                )
            )
        else:
            session.add(
                Repository(
                    organization_id=uuid4(),
                    github_repository_id=1,
                    full_name="unknown/repository",
                    display_name="unknown/repository",
                    default_branch="main",
                    importance="low",
                    last_synced_at=REFERENCE_DATA_AS_OF,
                )
            )
        session.commit()


def test_database_url_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        database_url_from_environment()
