"""add structured risk acceptance lifecycle

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "remediation_actions",
        sa.Column(
            "reason_code",
            sa.String(length=40),
            nullable=True,
            comment="위험 수용의 구조화된 사유 코드",
        ),
    )
    op.add_column(
        "remediation_actions",
        sa.Column(
            "revoked_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="위험 수용을 취소하고 재검토를 연 시각",
        ),
    )
    op.add_column(
        "remediation_actions",
        sa.Column(
            "revoked_by_user_id",
            sa.Uuid(),
            nullable=True,
            comment="위험 수용을 취소한 사용자 식별자",
        ),
    )
    op.add_column(
        "remediation_actions",
        sa.Column(
            "revocation_note",
            sa.Text(),
            nullable=True,
            comment="위험 수용 취소 시 남긴 선택 메모",
        ),
    )
    op.execute(
        "UPDATE remediation_actions SET reason_code = 'other' "
        "WHERE action_type = 'risk_accepted'"
    )
    op.alter_column("remediation_actions", "note", nullable=True)
    op.execute(
        """
        DO $$
        DECLARE existing_constraint text;
        BEGIN
            SELECT constraint_name INTO existing_constraint
            FROM information_schema.table_constraints
            WHERE table_schema = current_schema()
              AND table_name = 'remediation_actions'
              AND constraint_type = 'UNIQUE'
              AND constraint_name <> 'uq_remediation_actions_organization_id_id'
            LIMIT 1;
            IF existing_constraint IS NOT NULL THEN
                EXECUTE format(
                    'ALTER TABLE remediation_actions DROP CONSTRAINT %I',
                    existing_constraint
                );
            END IF;
        END $$;
        """
    )
    op.create_index(
        "uq_remediation_actions_active_target_fingerprint",
        "remediation_actions",
        ["organization_id", "group_key", "action_type", "target_fingerprint"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    op.create_foreign_key(
        "fk_remediation_actions_revoked_by_user",
        "remediation_actions",
        "users",
        ["organization_id", "revoked_by_user_id"],
        ["organization_id", "id"],
    )
    op.create_check_constraint(
        "ck_remediation_actions_reason_code_values",
        "remediation_actions",
        "reason_code IS NULL OR reason_code IN "
        "('compatibility_blocked', 'low_current_impact', 'other')",
    )
    op.create_check_constraint(
        "ck_remediation_actions_risk_reason_required",
        "remediation_actions",
        "(action_type = 'risk_accepted' AND reason_code IS NOT NULL) OR "
        "(action_type = 'remediation_requested' AND reason_code IS NULL)",
    )
    op.create_check_constraint(
        "ck_remediation_actions_other_note_required",
        "remediation_actions",
        "reason_code <> 'other' OR (note IS NOT NULL AND length(trim(note)) > 0)",
    )
    op.create_check_constraint(
        "ck_remediation_actions_revocation_consistency",
        "remediation_actions",
        "(revoked_at IS NULL AND revoked_by_user_id IS NULL) OR "
        "(revoked_at IS NOT NULL AND revoked_by_user_id IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_remediation_actions_revocation_consistency",
        "remediation_actions",
        type_="check",
    )
    op.drop_constraint(
        "ck_remediation_actions_other_note_required",
        "remediation_actions",
        type_="check",
    )
    op.drop_constraint(
        "ck_remediation_actions_risk_reason_required",
        "remediation_actions",
        type_="check",
    )
    op.drop_constraint(
        "ck_remediation_actions_reason_code_values",
        "remediation_actions",
        type_="check",
    )
    op.drop_constraint(
        "fk_remediation_actions_revoked_by_user",
        "remediation_actions",
        type_="foreignkey",
    )
    op.drop_index(
        "uq_remediation_actions_active_target_fingerprint",
        table_name="remediation_actions",
    )
    op.create_unique_constraint(
        "uq_remediation_actions_target_fingerprint",
        "remediation_actions",
        ["organization_id", "group_key", "action_type", "target_fingerprint"],
    )
    op.execute(
        "UPDATE remediation_actions SET note = COALESCE(note, reason_code, '위험 수용')"
    )
    op.alter_column("remediation_actions", "note", nullable=False)
    op.drop_column("remediation_actions", "revocation_note")
    op.drop_column("remediation_actions", "revoked_by_user_id")
    op.drop_column("remediation_actions", "revoked_at")
    op.drop_column("remediation_actions", "reason_code")
