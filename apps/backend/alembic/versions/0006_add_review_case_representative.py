"""add Review Case representative Candidate and Batch

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _require_empty_review_cases() -> None:
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM review_cases) THEN
                    RAISE EXCEPTION
                        '대표 Candidate와 Batch를 추측할 수 없으므로 review_cases를 비운 뒤 Migration해야 합니다.';
                END IF;
            END
            $$;
            """
        )
    )


def upgrade() -> None:
    _require_empty_review_cases()
    op.add_column(
        "review_cases",
        sa.Column(
            "representative_candidate_id",
            sa.Uuid(),
            nullable=False,
            comment="Case 목록과 상단 요약에 사용하는 대표 Candidate 식별자",
        ),
    )
    op.add_column(
        "review_cases",
        sa.Column(
            "representative_batch_id",
            sa.Uuid(),
            nullable=False,
            comment="대표 Candidate를 전달한 Gold Batch 식별자",
        ),
    )
    op.create_foreign_key(
        op.f(
            "fk_review_cases_representative_batch_id_representative_candidate_id_"
            "gold_batch_candidates"
        ),
        "review_cases",
        "gold_batch_candidates",
        ["representative_batch_id", "representative_candidate_id"],
        ["batch_id", "candidate_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f(
            "fk_review_cases_representative_batch_id_representative_candidate_id_"
            "gold_batch_candidates"
        ),
        "review_cases",
        type_="foreignkey",
    )
    op.drop_column("review_cases", "representative_batch_id")
    op.drop_column("review_cases", "representative_candidate_id")
