"""align candidates to CVE matching

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                      FROM risk_candidates
                     WHERE cve_id IS NULL
                        OR subject_type <> 'CVE'
                        OR subject_id <> cve_id
                ) THEN
                    RAISE EXCEPTION
                        'CVE 기준으로 변환할 수 없는 Candidate가 있습니다.';
                END IF;
            END
            $$;
            """
        )
    )
    op.drop_constraint(
        op.f("ck_risk_candidates_subject_consistency"),
        "risk_candidates",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_risk_candidates_subject_type_values"),
        "risk_candidates",
        type_="check",
    )
    op.alter_column(
        "risk_candidates",
        "subject_type",
        existing_type=sa.String(length=10),
        existing_nullable=False,
        comment="Alert 연결 기준 종류이며 S1에서는 CVE",
    )
    op.alter_column(
        "risk_candidates",
        "subject_id",
        existing_type=sa.String(length=40),
        existing_nullable=False,
        comment="CVE 기준 공통 연결 식별자",
    )
    op.alter_column(
        "risk_candidates",
        "ghsa_id",
        existing_type=sa.String(length=40),
        nullable=True,
        comment="Gold 원본 GHSA 보조 식별자이며 없으면 null",
    )
    op.alter_column(
        "risk_candidates",
        "cve_id",
        existing_type=sa.String(length=32),
        nullable=False,
        comment="Alert 연결에 사용하는 필수 CVE 식별자",
    )
    op.create_check_constraint(
        op.f("ck_risk_candidates_subject_type_values"),
        "risk_candidates",
        "subject_type = 'CVE'",
    )
    op.create_check_constraint(
        op.f("ck_risk_candidates_subject_consistency"),
        "risk_candidates",
        "subject_type = 'CVE' AND subject_id = cve_id",
    )
    op.create_table_comment(
        "risk_candidates",
        "Gold가 선정한 CVE 기준 위험 변화 후보",
        existing_comment="Gold가 선정한 CVE 또는 GHSA 기준 위험 변화 후보",
    )
    op.create_table_comment(
        "alert_candidate_matches",
        "Dependabot Alert와 Gold 위험 후보의 CVE 매칭 결과",
        existing_comment="Dependabot Alert와 Gold 위험 후보의 CVE·GHSA 매칭 결과",
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM risk_candidates WHERE ghsa_id IS NULL) THEN
                    RAISE EXCEPTION
                        'GHSA가 없는 Candidate가 있으면 downgrade할 수 없습니다.';
                END IF;
            END
            $$;
            """
        )
    )
    op.drop_constraint(
        op.f("ck_risk_candidates_subject_consistency"),
        "risk_candidates",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_risk_candidates_subject_type_values"),
        "risk_candidates",
        type_="check",
    )
    op.alter_column(
        "risk_candidates",
        "cve_id",
        existing_type=sa.String(length=32),
        nullable=True,
        comment="연결된 CVE 식별자이며 GHSA-only 후보이면 null",
    )
    op.alter_column(
        "risk_candidates",
        "ghsa_id",
        existing_type=sa.String(length=40),
        nullable=False,
        comment="Gold 원본 GHSA 식별자",
    )
    op.alter_column(
        "risk_candidates",
        "subject_id",
        existing_type=sa.String(length=40),
        existing_nullable=False,
        comment="subject_type에 따른 CVE 또는 GHSA 공통 연결 식별자",
    )
    op.alter_column(
        "risk_candidates",
        "subject_type",
        existing_type=sa.String(length=10),
        existing_nullable=False,
        comment="Alert 연결 기준 종류이며 CVE 또는 GHSA",
    )
    op.create_check_constraint(
        op.f("ck_risk_candidates_subject_type_values"),
        "risk_candidates",
        "subject_type IN ('CVE', 'GHSA')",
    )
    op.create_check_constraint(
        op.f("ck_risk_candidates_subject_consistency"),
        "risk_candidates",
        "(subject_type = 'CVE' AND cve_id IS NOT NULL AND subject_id = cve_id) OR "
        "(subject_type = 'GHSA' AND cve_id IS NULL AND subject_id = ghsa_id)",
    )
    op.create_table_comment(
        "risk_candidates",
        "Gold가 선정한 CVE 또는 GHSA 기준 위험 변화 후보",
        existing_comment="Gold가 선정한 CVE 기준 위험 변화 후보",
    )
    op.create_table_comment(
        "alert_candidate_matches",
        "Dependabot Alert와 Gold 위험 후보의 CVE·GHSA 매칭 결과",
        existing_comment="Dependabot Alert와 Gold 위험 후보의 CVE 매칭 결과",
    )
