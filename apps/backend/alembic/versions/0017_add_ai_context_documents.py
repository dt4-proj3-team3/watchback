"""add AI context documents

Revision ID: 0017
Revises: 0016
Create Date: 2026-09-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_context_documents",
        sa.Column("id", sa.Uuid(), nullable=False, comment="AI 분석 문서 내부 식별자"),
        sa.Column(
            "organization_id",
            sa.Uuid(),
            nullable=False,
            comment="AI 분석 문서가 속한 조직 식별자",
        ),
        sa.Column(
            "group_key",
            sa.String(length=64),
            nullable=False,
            comment="조직·ecosystem·패키지로 계산한 조치 그룹 키",
        ),
        sa.Column(
            "ecosystem",
            sa.String(length=50),
            nullable=False,
            comment="분석 대상 패키지 생태계",
        ),
        sa.Column(
            "package_name",
            sa.String(length=255),
            nullable=False,
            comment="분석 대상 패키지 이름",
        ),
        sa.Column(
            "document_type",
            sa.String(length=50),
            nullable=False,
            comment="저장소 사용 단서 또는 업데이트 변경 정보 구분",
        ),
        sa.Column(
            "content",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="근거와 한계를 보존한 구조화 분석 결과",
        ),
        sa.Column(
            "source_revision",
            sa.String(length=255),
            nullable=False,
            comment="분석에 사용한 저장소 commit 또는 패키지 버전 식별자",
        ),
        sa.Column(
            "source_url",
            sa.Text(),
            nullable=True,
            comment="공식 원문 또는 릴리스 정보 URL",
        ),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="분석 문서를 생성한 시각",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="운영 DB에 분석 문서를 최초 저장한 시각",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="운영 DB에서 분석 문서를 마지막으로 갱신한 시각",
        ),
        sa.CheckConstraint(
            "document_type IN ('usage_indicators', 'upgrade_notes')",
            name=op.f("ck_ai_context_documents_document_type_values"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_ai_context_documents_organization_id_organizations"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_context_documents")),
        sa.UniqueConstraint(
            "organization_id",
            "group_key",
            "document_type",
            name=op.f(
                "uq_ai_context_documents_organization_id_group_key_document_type"
            ),
        ),
        comment="패키지 조치 판단을 위해 백필한 저장소 단서와 업데이트 정보",
    )
    op.create_index(
        op.f("ix_ai_context_documents_organization_package"),
        "ai_context_documents",
        ["organization_id", "ecosystem", "package_name"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_ai_context_documents_organization_package"),
        table_name="ai_context_documents",
    )
    op.drop_table("ai_context_documents")
