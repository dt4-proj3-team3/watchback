"""add remediation target lifecycle

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "remediation_action_targets",
        sa.Column(
            "revoked_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="개별 조치 대상의 위험 수용을 취소한 시각",
        ),
    )
    op.add_column(
        "remediation_action_targets",
        sa.Column(
            "revoked_by_user_id",
            sa.Uuid(),
            nullable=True,
            comment="개별 조치 대상의 위험 수용을 취소한 사용자",
        ),
    )
    op.add_column(
        "remediation_action_targets",
        sa.Column(
            "revocation_note",
            sa.Text(),
            nullable=True,
            comment="개별 조치 대상의 위험 수용 취소 메모",
        ),
    )
    op.create_foreign_key(
        "fk_remediation_targets_revoked_by_user",
        "remediation_action_targets",
        "users",
        ["organization_id", "revoked_by_user_id"],
        ["organization_id", "id"],
    )
    op.create_check_constraint(
        "ck_remediation_targets_revocation_consistency",
        "remediation_action_targets",
        "(revoked_at IS NULL AND revoked_by_user_id IS NULL) OR "
        "(revoked_at IS NOT NULL AND revoked_by_user_id IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_remediation_targets_revocation_consistency",
        "remediation_action_targets",
        type_="check",
    )
    op.drop_constraint(
        "fk_remediation_targets_revoked_by_user",
        "remediation_action_targets",
        type_="foreignkey",
    )
    op.drop_column("remediation_action_targets", "revocation_note")
    op.drop_column("remediation_action_targets", "revoked_by_user_id")
    op.drop_column("remediation_action_targets", "revoked_at")
