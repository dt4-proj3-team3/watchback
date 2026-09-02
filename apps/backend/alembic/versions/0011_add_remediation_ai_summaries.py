"""add persisted remediation AI summaries

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "remediation_ai_summaries",
        sa.Column("id", sa.Uuid(), nullable=False, comment="AI 요약 내부 식별자"),
        sa.Column("organization_id", sa.Uuid(), nullable=False, comment="AI 요약이 속한 조직 식별자"),
        sa.Column("group_key", sa.String(length=64), nullable=False, comment="조직·ecosystem·패키지로 계산한 조치 그룹 키"),
        sa.Column("ecosystem", sa.String(length=50), nullable=False, comment="요약 대상 패키지 생태계"),
        sa.Column("package_name", sa.String(length=255), nullable=False, comment="요약 대상 패키지 이름"),
        sa.Column("prompt_version", sa.String(length=50), nullable=False, comment="요약 생성에 사용한 프롬프트 버전"),
        sa.Column("risk_summary", sa.Text(), nullable=False, comment="사용자에게 표시할 핵심 위험 요약"),
        sa.Column("action_summary", sa.Text(), nullable=False, comment="사용자에게 표시할 권장 조치 요약"),
        sa.Column("model", sa.String(length=100), nullable=False, comment="요약 생성에 사용한 Azure OpenAI 배포 모델"),
        sa.Column("source_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment="요약 생성에 사용한 Watchback 근거 식별자 목록"),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False, comment="AI 요약을 생성한 시각"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False, comment="운영 DB에 AI 요약을 최초 저장한 시각"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False, comment="운영 DB에서 AI 요약을 마지막으로 갱신한 시각"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], name=op.f("fk_remediation_ai_summaries_organization_id_organizations")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_remediation_ai_summaries")),
        sa.UniqueConstraint("organization_id", "group_key", name=op.f("uq_remediation_ai_summaries_organization_id_group_key")),
        comment="패키지 조치 그룹별로 일괄 생성해 영구 저장한 AI 요약",
    )
    op.create_index("ix_remediation_ai_summaries_organization_package", "remediation_ai_summaries", ["organization_id", "ecosystem", "package_name"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_remediation_ai_summaries_organization_package", table_name="remediation_ai_summaries")
    op.drop_table("remediation_ai_summaries")
