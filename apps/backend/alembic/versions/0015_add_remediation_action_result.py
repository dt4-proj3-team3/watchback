"""add remediation action result

Revision ID: 0015
Revises: 0014
Create Date: 2026-09-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "remediation_actions",
        sa.Column(
            "result",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="자동조치 실행 결과와 생성된 GitHub PR 정보",
        ),
    )


def downgrade() -> None:
    op.drop_column("remediation_actions", "result")
