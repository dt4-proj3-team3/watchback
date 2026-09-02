"""add AI summary interpretation note

Revision ID: 0014
Revises: 0013
Create Date: 2026-09-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "remediation_ai_summaries",
        sa.Column(
            "interpretation_note",
            sa.Text(),
            nullable=True,
            comment="검토된 EPSS 모델·소스 변동과 겹치는 요약의 해석 주의 문구",
        ),
    )


def downgrade() -> None:
    op.drop_column("remediation_ai_summaries", "interpretation_note")
