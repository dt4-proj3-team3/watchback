"""align Dependabot source enums

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-21
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        op.f("ck_security_advisories_severity_values"),
        "security_advisories",
        type_="check",
    )
    op.execute("UPDATE security_advisories SET severity = 'medium' WHERE severity = 'moderate'")
    op.create_check_constraint(
        op.f("ck_security_advisories_severity_values"),
        "security_advisories",
        "severity IN ('low', 'medium', 'high', 'critical')",
    )

    op.drop_constraint(
        op.f("ck_dependabot_alerts_dependency_relationship_values"),
        "dependabot_alerts",
        type_="check",
    )
    op.execute(
        "UPDATE dependabot_alerts SET dependency_relationship = 'transitive' "
        "WHERE dependency_relationship = 'indirect'"
    )
    op.create_check_constraint(
        op.f("ck_dependabot_alerts_dependency_relationship_values"),
        "dependabot_alerts",
        "dependency_relationship IS NULL OR "
        "dependency_relationship IN ('direct', 'transitive', 'unknown')",
    )

    op.drop_constraint(
        op.f("ck_dependabot_alerts_state_timestamp_consistency"),
        "dependabot_alerts",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_dependabot_alerts_state_values"),
        "dependabot_alerts",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_dependabot_alerts_state_values"),
        "dependabot_alerts",
        "state IN ('open', 'dismissed', 'fixed', 'auto_dismissed')",
    )
    op.create_check_constraint(
        op.f("ck_dependabot_alerts_state_timestamp_consistency"),
        "dependabot_alerts",
        "(state = 'open' AND dismissed_at IS NULL AND fixed_at IS NULL "
        "AND auto_dismissed_at IS NULL) OR "
        "(state = 'dismissed' AND dismissed_at IS NOT NULL) OR "
        "(state = 'fixed' AND fixed_at IS NOT NULL) OR "
        "(state = 'auto_dismissed' AND auto_dismissed_at IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_dependabot_alerts_state_timestamp_consistency"),
        "dependabot_alerts",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_dependabot_alerts_state_values"),
        "dependabot_alerts",
        type_="check",
    )
    op.execute(
        "UPDATE dependabot_alerts "
        "SET state = 'dismissed', dismissed_at = COALESCE(dismissed_at, auto_dismissed_at) "
        "WHERE state = 'auto_dismissed'"
    )
    op.create_check_constraint(
        op.f("ck_dependabot_alerts_state_values"),
        "dependabot_alerts",
        "state IN ('open', 'dismissed', 'fixed')",
    )
    op.create_check_constraint(
        op.f("ck_dependabot_alerts_state_timestamp_consistency"),
        "dependabot_alerts",
        "(state = 'open' AND dismissed_at IS NULL AND fixed_at IS NULL) OR "
        "(state = 'dismissed' AND dismissed_at IS NOT NULL) OR "
        "(state = 'fixed' AND fixed_at IS NOT NULL)",
    )

    op.drop_constraint(
        op.f("ck_dependabot_alerts_dependency_relationship_values"),
        "dependabot_alerts",
        type_="check",
    )
    op.execute(
        "UPDATE dependabot_alerts SET dependency_relationship = 'indirect' "
        "WHERE dependency_relationship = 'transitive'"
    )
    op.execute(
        "UPDATE dependabot_alerts SET dependency_relationship = NULL "
        "WHERE dependency_relationship = 'unknown'"
    )
    op.create_check_constraint(
        op.f("ck_dependabot_alerts_dependency_relationship_values"),
        "dependabot_alerts",
        "dependency_relationship IS NULL OR dependency_relationship IN ('direct', 'indirect')",
    )

    op.drop_constraint(
        op.f("ck_security_advisories_severity_values"),
        "security_advisories",
        type_="check",
    )
    op.execute("UPDATE security_advisories SET severity = 'moderate' WHERE severity = 'medium'")
    op.create_check_constraint(
        op.f("ck_security_advisories_severity_values"),
        "security_advisories",
        "severity IN ('low', 'moderate', 'high', 'critical')",
    )
