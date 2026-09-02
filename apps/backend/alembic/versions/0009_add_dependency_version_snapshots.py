"""add dependency version snapshots

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "dependency_version_snapshots",
        sa.Column(
            "id",
            sa.Uuid(),
            nullable=False,
            comment="실제 사용 버전 Snapshot 내부 식별자",
        ),
        sa.Column(
            "organization_id",
            sa.Uuid(),
            nullable=False,
            comment="Snapshot이 속한 조직 식별자",
        ),
        sa.Column(
            "repository_id",
            sa.Uuid(),
            nullable=False,
            comment="버전을 수집한 저장소 식별자",
        ),
        sa.Column(
            "manifest_path",
            sa.String(length=500),
            nullable=True,
            comment="Dependabot Alert가 가리킨 manifest 경로",
        ),
        sa.Column(
            "commit_sha",
            sa.String(length=64),
            nullable=False,
            comment="파일을 조회한 저장소 commit SHA",
        ),
        sa.Column(
            "ecosystem",
            sa.String(length=50),
            nullable=False,
            comment="패키지 생태계 이름",
        ),
        sa.Column(
            "package_name",
            sa.String(length=255),
            nullable=False,
            comment="실제 버전을 확인한 패키지 이름",
        ),
        sa.Column(
            "resolved_versions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="lockfile에서 확인한 실제 사용 버전 목록",
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            comment="단일·복수 버전 확인 또는 확인 불가 상태",
        ),
        sa.Column(
            "reason",
            sa.String(length=50),
            nullable=True,
            comment="확인 불가 또는 파싱 실패의 상세 사유",
        ),
        sa.Column(
            "source_path",
            sa.String(length=500),
            nullable=True,
            comment="실제 버전을 읽은 lockfile 경로",
        ),
        sa.Column(
            "source_blob_sha",
            sa.String(length=64),
            nullable=True,
            comment="실제 버전을 읽은 Git blob SHA",
        ),
        sa.Column(
            "observed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="GitHub에서 실제 버전을 수집한 시각",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="운영 DB에 Snapshot을 생성한 시각",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="운영 DB에서 Snapshot을 마지막으로 수정한 시각",
        ),
        sa.CheckConstraint(
            "reason IS NULL OR reason IN ("
            "'unsupported_manifest', 'lockfile_not_found', "
            "'package_not_found', 'invalid_lockfile')",
            name=op.f("ck_dependency_version_snapshots_reason_values"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(resolved_versions) = 'array'",
            name=op.f("ck_dependency_version_snapshots_resolved_versions_array"),
        ),
        sa.CheckConstraint(
            "(status = 'resolved' AND jsonb_array_length(resolved_versions) = 1 "
            "AND reason IS NULL) OR "
            "(status = 'multiple' AND jsonb_array_length(resolved_versions) > 1 "
            "AND reason IS NULL) OR "
            "(status = 'unavailable' AND jsonb_array_length(resolved_versions) = 0 "
            "AND reason IN ('unsupported_manifest', 'lockfile_not_found', "
            "'package_not_found')) OR "
            "(status = 'invalid' AND jsonb_array_length(resolved_versions) = 0 "
            "AND reason = 'invalid_lockfile')",
            name=op.f("ck_dependency_version_snapshots_resolution_consistency"),
        ),
        sa.CheckConstraint(
            "status IN ('resolved', 'multiple', 'unavailable', 'invalid')",
            name=op.f("ck_dependency_version_snapshots_status_values"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "repository_id"],
            ["repositories.organization_id", "repositories.id"],
            name=op.f(
                "fk_dependency_version_snapshots_organization_id_repository_id_repositories"
            ),
        ),
        sa.PrimaryKeyConstraint(
            "id", name=op.f("pk_dependency_version_snapshots")
        ),
        comment="저장소 commit 기준 의존성 실제 사용 버전 수집 결과",
    )
    op.create_index(
        "ix_dependency_version_snapshots_repository_observed",
        "dependency_version_snapshots",
        ["repository_id", "observed_at"],
        unique=False,
    )
    op.create_index(
        "uq_dependency_version_snapshots_identity",
        "dependency_version_snapshots",
        [
            "repository_id",
            "manifest_path",
            "commit_sha",
            "ecosystem",
            "package_name",
        ],
        unique=True,
        postgresql_nulls_not_distinct=True,
    )


def downgrade() -> None:
    op.drop_index(
        "uq_dependency_version_snapshots_identity",
        table_name="dependency_version_snapshots",
        postgresql_nulls_not_distinct=True,
    )
    op.drop_index(
        "ix_dependency_version_snapshots_repository_observed",
        table_name="dependency_version_snapshots",
    )
    op.drop_table("dependency_version_snapshots")
