"""add repository display name

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-21
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "repositories",
        sa.Column(
            "display_name",
            sa.String(length=255),
            nullable=True,
            comment="화면에 표시할 가상 회사 기준 저장소 이름",
        ),
    )
    op.execute(
        "UPDATE repositories SET display_name = full_name WHERE display_name IS NULL"
    )
    op.alter_column("repositories", "display_name", nullable=False)


def downgrade() -> None:
    op.drop_column("repositories", "display_name")
