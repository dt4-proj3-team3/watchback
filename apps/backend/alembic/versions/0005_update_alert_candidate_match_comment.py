"""update Alert-Candidate match comment

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-26
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table_comment(
        "alert_candidate_matches",
        "Dependabot Alert와 Gold 위험 후보의 CVE·GHSA 매칭 결과",
        existing_comment="Dependabot Alert Advisory의 CVE와 위험 후보의 매칭 결과",
    )


def downgrade() -> None:
    op.create_table_comment(
        "alert_candidate_matches",
        "Dependabot Alert Advisory의 CVE와 위험 후보의 매칭 결과",
        existing_comment="Dependabot Alert와 Gold 위험 후보의 CVE·GHSA 매칭 결과",
    )
