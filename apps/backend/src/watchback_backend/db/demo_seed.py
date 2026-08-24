from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import Engine, create_engine, select
from sqlalchemy.orm import Session

from watchback_backend.db.models import Organization, Repository, User


REFERENCE_DATA_AS_OF = datetime(2026, 8, 20, 7, 30, tzinfo=UTC)

ORGANIZATION = {
    "id": uuid5(NAMESPACE_URL, "watchback:demo:organization:github:dt4-proj3-team3"),
    "github_organization_id": 314105294,
    "github_login": "dt4-proj3-team3",
    "display_name": "노바링크",
}

USERS = (
    {
        "id": uuid5(NAMESPACE_URL, "watchback:demo:user:seoyeon.kim@novalink.example"),
        "email": "seoyeon.kim@novalink.example",
        "display_name": "김서연",
    },
    {
        "id": uuid5(NAMESPACE_URL, "watchback:demo:user:junho.park@novalink.example"),
        "email": "junho.park@novalink.example",
        "display_name": "박준호",
    },
)

REPOSITORIES = (
    {
        "id": uuid5(NAMESPACE_URL, "watchback:demo:repository:github:1329314801"),
        "github_repository_id": 1329314801,
        "full_name": "dt4-proj3-team3/watchback-vulnerable-fe-lab",
        "display_name": "novalink/customer-fe",
        "default_branch": "main",
        "importance": "critical",
        "github_updated_at": datetime(2026, 8, 20, 7, 13, 2, tzinfo=UTC),
    },
    {
        "id": uuid5(NAMESPACE_URL, "watchback:demo:repository:github:1340408606"),
        "github_repository_id": 1340408606,
        "full_name": "dt4-proj3-team3/watchback-vulnerable-be-lab",
        "display_name": "novalink/ai-platform-api",
        "default_branch": "main",
        "importance": "high",
        "github_updated_at": datetime(2026, 8, 20, 7, 29, 53, tzinfo=UTC),
    },
)


class SeedConflictError(RuntimeError):
    """기준 데이터의 외부 식별자가 서로 다른 기존 행을 가리킬 때 발생한다."""


@dataclass(frozen=True)
class EntityCounts:
    created: int = 0
    updated: int = 0
    unchanged: int = 0


@dataclass(frozen=True)
class DemoSeedResult:
    organization: EntityCounts
    users: EntityCounts
    repositories: EntityCounts
    organization_id: UUID
    user_ids: dict[str, UUID]
    repository_ids: dict[str, UUID]

    def as_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, default=str, sort_keys=True)


def _counts(outcomes: list[str]) -> EntityCounts:
    return EntityCounts(
        created=outcomes.count("created"),
        updated=outcomes.count("updated"),
        unchanged=outcomes.count("unchanged"),
    )


def _set_values(instance: object, values: dict[str, object]) -> bool:
    changed = False
    for field, value in values.items():
        if getattr(instance, field) != value:
            setattr(instance, field, value)
            changed = True
    return changed


def _seed_organization(session: Session) -> tuple[Organization, str]:
    by_github_id = session.scalar(
        select(Organization).where(
            Organization.github_organization_id == ORGANIZATION["github_organization_id"]
        )
    )
    by_login = session.scalar(
        select(Organization).where(Organization.github_login == ORGANIZATION["github_login"])
    )

    if by_github_id is not None and by_login is not None and by_github_id.id != by_login.id:
        raise SeedConflictError("GitHub 조직 ID와 login이 서로 다른 조직 행에 연결되어 있습니다.")
    if by_github_id is not None and by_github_id.github_login != ORGANIZATION["github_login"]:
        raise SeedConflictError("기존 GitHub 조직 ID의 login이 기준 데이터와 다릅니다.")
    if by_login is not None and (
        by_login.github_organization_id != ORGANIZATION["github_organization_id"]
    ):
        raise SeedConflictError("기존 GitHub 조직 login의 ID가 기준 데이터와 다릅니다.")

    organization = by_github_id or by_login
    if organization is None:
        organization = Organization(**ORGANIZATION)
        session.add(organization)
        return organization, "created"

    changed = _set_values(
        organization,
        {"display_name": ORGANIZATION["display_name"]},
    )
    return organization, "updated" if changed else "unchanged"


def _seed_users(session: Session, organization: Organization) -> tuple[list[str], dict[str, UUID]]:
    outcomes: list[str] = []
    identifiers: dict[str, UUID] = {}

    for definition in USERS:
        user = session.scalar(
            select(User).where(
                User.organization_id == organization.id,
                User.email == definition["email"],
            )
        )
        if user is None:
            user = User(
                id=definition["id"],
                organization_id=organization.id,
                github_user_id=None,
                email=definition["email"],
                display_name=definition["display_name"],
                is_demo=True,
            )
            session.add(user)
            outcome = "created"
        else:
            changed = _set_values(
                user,
                {
                    "github_user_id": None,
                    "display_name": definition["display_name"],
                    "is_demo": True,
                },
            )
            outcome = "updated" if changed else "unchanged"

        outcomes.append(outcome)
        identifiers[definition["email"]] = user.id

    return outcomes, identifiers


def _seed_repositories(
    session: Session, organization: Organization
) -> tuple[list[str], dict[str, UUID]]:
    outcomes: list[str] = []
    identifiers: dict[str, UUID] = {}

    for definition in REPOSITORIES:
        by_github_id = session.scalar(
            select(Repository).where(
                Repository.organization_id == organization.id,
                Repository.github_repository_id == definition["github_repository_id"],
            )
        )
        by_full_name = session.scalar(
            select(Repository).where(Repository.full_name == definition["full_name"])
        )

        if (
            by_github_id is not None
            and by_full_name is not None
            and by_github_id.id != by_full_name.id
        ):
            raise SeedConflictError("GitHub 저장소 ID와 full_name이 서로 다른 행에 연결되어 있습니다.")
        if by_full_name is not None and (
            by_full_name.organization_id != organization.id
            or by_full_name.github_repository_id != definition["github_repository_id"]
        ):
            raise SeedConflictError("기준 저장소 full_name이 다른 조직 또는 GitHub ID에 연결되어 있습니다.")

        repository = by_github_id or by_full_name
        if repository is None:
            repository = Repository(
                id=definition["id"],
                organization_id=organization.id,
                github_repository_id=definition["github_repository_id"],
                full_name=definition["full_name"],
                display_name=definition["display_name"],
                default_branch=definition["default_branch"],
                importance=definition["importance"],
                github_updated_at=definition["github_updated_at"],
                last_synced_at=REFERENCE_DATA_AS_OF,
            )
            session.add(repository)
            outcome = "created"
        else:
            # GitHub 동기화가 관리하는 원본 필드는 재실행 시 이전 값으로 되돌리지 않는다.
            changed = _set_values(
                repository,
                {
                    "display_name": definition["display_name"],
                    "importance": definition["importance"],
                },
            )
            outcome = "updated" if changed else "unchanged"

        outcomes.append(outcome)
        identifiers[definition["full_name"]] = repository.id

    return outcomes, identifiers


def seed_demo_reference_data(session: Session) -> DemoSeedResult:
    """시연용 조직·사용자·저장소를 하나의 트랜잭션으로 생성하거나 갱신한다."""

    with session.begin():
        organization, organization_outcome = _seed_organization(session)
        user_outcomes, user_ids = _seed_users(session, organization)
        repository_outcomes, repository_ids = _seed_repositories(session, organization)
        result = DemoSeedResult(
            organization=_counts([organization_outcome]),
            users=_counts(user_outcomes),
            repositories=_counts(repository_outcomes),
            organization_id=organization.id,
            user_ids=user_ids,
            repository_ids=repository_ids,
        )

    return result


def database_url_from_environment() -> str:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL 환경변수가 필요합니다.")
    return database_url


def seed_database(engine: Engine) -> DemoSeedResult:
    with Session(engine) as session:
        return seed_demo_reference_data(session)


def main() -> None:
    try:
        engine = create_engine(database_url_from_environment())
        result = seed_database(engine)
    except (RuntimeError, SeedConflictError) as error:
        raise SystemExit(str(error)) from error
    finally:
        if "engine" in locals():
            engine.dispose()

    print(result.as_json())


if __name__ == "__main__":
    main()
