"""add cancelled remediation state

Revision ID: 0016
Revises: 0015
Create Date: 2026-09-02
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        op.f("ck_remediation_actions_type_state_consistency"),
        "remediation_actions",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_remediation_actions_watchback_state_values"),
        "remediation_actions",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_remediation_actions_watchback_state_values"),
        "remediation_actions",
        "watchback_state IN ('accepted', 'requested', 'pr_open', 'pr_merged', "
        "'verification_pending', 'completed', 'cancelled', 'failed')",
    )
    op.create_check_constraint(
        op.f("ck_remediation_actions_type_state_consistency"),
        "remediation_actions",
        "(action_type = 'risk_accepted' AND watchback_state = 'accepted') OR "
        "(action_type = 'remediation_requested' AND watchback_state IN ("
        "'requested', 'pr_open', 'pr_merged', 'verification_pending', "
        "'completed', 'cancelled', 'failed'))",
    )


def downgrade() -> None:
    op.execute(
        "UPDATE remediation_actions SET watchback_state = 'requested' "
        "WHERE watchback_state = 'cancelled'"
    )
    op.drop_constraint(
        op.f("ck_remediation_actions_type_state_consistency"),
        "remediation_actions",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_remediation_actions_watchback_state_values"),
        "remediation_actions",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_remediation_actions_watchback_state_values"),
        "remediation_actions",
        "watchback_state IN ('accepted', 'requested', 'pr_open', 'pr_merged', "
        "'verification_pending', 'completed', 'failed')",
    )
    op.create_check_constraint(
        op.f("ck_remediation_actions_type_state_consistency"),
        "remediation_actions",
        "(action_type = 'risk_accepted' AND watchback_state = 'accepted') OR "
        "(action_type = 'remediation_requested' AND watchback_state IN ("
        "'requested', 'pr_open', 'pr_merged', 'verification_pending', "
        "'completed', 'failed'))",
    )
