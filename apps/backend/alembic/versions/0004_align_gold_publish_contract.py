"""align Gold Publish View contract

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _require_empty_gold_tables(direction: str) -> None:
    op.execute(
        sa.text(
            f"""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM gold_batches)
                   OR EXISTS (SELECT 1 FROM risk_candidates)
                   OR EXISTS (SELECT 1 FROM gold_batch_candidates)
                   OR EXISTS (SELECT 1 FROM candidate_evidence) THEN
                    RAISE EXCEPTION
                        'Gold 계약 {direction} 전환 전에 Gold 동기화 영역을 비워야 합니다.';
                END IF;
            END
            $$;
            """
        )
    )


def upgrade() -> None:
    _require_empty_gold_tables("upgrade")

    op.add_column(
        "gold_batches",
        sa.Column(
            "ds_run_id",
            sa.String(length=255),
            nullable=True,
            comment="DS 실행을 추적하는 선택적 식별자",
        ),
    )

    op.drop_constraint(
        op.f("ck_risk_candidates_priority_values"),
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
        "priority",
        existing_type=sa.String(length=20),
        comment="Gold가 부여한 P0~P3 후보 우선순위",
    )
    op.add_column(
        "risk_candidates",
        sa.Column(
            "subject_type",
            sa.String(length=10),
            nullable=False,
            comment="Alert 연결 기준 종류이며 CVE 또는 GHSA",
        ),
    )
    op.add_column(
        "risk_candidates",
        sa.Column(
            "subject_id",
            sa.String(length=40),
            nullable=False,
            comment="subject_type에 따른 CVE 또는 GHSA 공통 연결 식별자",
        ),
    )
    op.add_column(
        "risk_candidates",
        sa.Column(
            "ghsa_id",
            sa.String(length=40),
            nullable=False,
            comment="Gold 원본 GHSA 식별자",
        ),
    )
    op.create_index(
        op.f("ix_risk_candidates_subject_id"),
        "risk_candidates",
        ["subject_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_risk_candidates_ghsa_id"),
        "risk_candidates",
        ["ghsa_id"],
        unique=False,
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
    op.create_check_constraint(
        op.f("ck_risk_candidates_priority_values"),
        "risk_candidates",
        "priority IN ('P0', 'P1', 'P2', 'P3')",
    )
    op.create_table_comment(
        "risk_candidates",
        "Gold가 선정한 CVE 또는 GHSA 기준 위험 변화 후보",
        existing_comment="Gold가 선정한 CVE 기준 위험 변화 후보",
    )

    op.drop_constraint(
        op.f("uq_candidate_evidence_source_evidence_id"),
        "candidate_evidence",
        type_="unique",
    )
    op.drop_constraint(
        op.f("fk_candidate_evidence_candidate_id_risk_candidates"),
        "candidate_evidence",
        type_="foreignkey",
    )
    op.add_column(
        "candidate_evidence",
        sa.Column(
            "batch_id",
            sa.Uuid(),
            nullable=False,
            comment="Evidence가 포함된 Gold Batch 식별자",
        ),
    )
    op.add_column(
        "candidate_evidence",
        sa.Column(
            "evidence_summary",
            sa.Text(),
            nullable=False,
            comment="Web 상세 화면에 표시할 근거 설명",
        ),
    )
    op.alter_column(
        "candidate_evidence",
        "current_value",
        existing_type=sa.Text(),
        nullable=True,
    )
    op.create_unique_constraint(
        op.f("uq_candidate_evidence_batch_id_source_evidence_id"),
        "candidate_evidence",
        ["batch_id", "source_evidence_id"],
    )
    op.create_foreign_key(
        op.f("fk_candidate_evidence_batch_id_candidate_id_gold_batch_candidates"),
        "candidate_evidence",
        "gold_batch_candidates",
        ["batch_id", "candidate_id"],
        ["batch_id", "candidate_id"],
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM risk_candidates
                     WHERE cve_id IS NULL OR subject_type <> 'CVE'
                ) THEN
                    RAISE EXCEPTION
                        'GHSA-only Candidate가 있으면 Gold 계약을 downgrade할 수 없습니다.';
                END IF;
                IF EXISTS (
                    SELECT source_evidence_id
                      FROM candidate_evidence
                     GROUP BY source_evidence_id
                    HAVING count(*) > 1
                ) THEN
                    RAISE EXCEPTION
                        'Batch 간 중복 evidence_id가 있으면 Gold 계약을 downgrade할 수 없습니다.';
                END IF;
            END
            $$;
            """
        )
    )

    op.drop_constraint(
        op.f("fk_candidate_evidence_batch_id_candidate_id_gold_batch_candidates"),
        "candidate_evidence",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("uq_candidate_evidence_batch_id_source_evidence_id"),
        "candidate_evidence",
        type_="unique",
    )
    op.alter_column(
        "candidate_evidence",
        "current_value",
        existing_type=sa.Text(),
        nullable=False,
    )
    op.drop_column("candidate_evidence", "evidence_summary")
    op.drop_column("candidate_evidence", "batch_id")
    op.create_foreign_key(
        op.f("fk_candidate_evidence_candidate_id_risk_candidates"),
        "candidate_evidence",
        "risk_candidates",
        ["candidate_id"],
        ["id"],
    )
    op.create_unique_constraint(
        op.f("uq_candidate_evidence_source_evidence_id"),
        "candidate_evidence",
        ["source_evidence_id"],
    )

    op.drop_constraint(
        op.f("ck_risk_candidates_priority_values"),
        "risk_candidates",
        type_="check",
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
    op.drop_index(op.f("ix_risk_candidates_ghsa_id"), table_name="risk_candidates")
    op.drop_index(op.f("ix_risk_candidates_subject_id"), table_name="risk_candidates")
    op.drop_column("risk_candidates", "ghsa_id")
    op.drop_column("risk_candidates", "subject_id")
    op.drop_column("risk_candidates", "subject_type")
    op.execute(
        """
        UPDATE risk_candidates
           SET priority = CASE priority
               WHEN 'P0' THEN 'critical'
               WHEN 'P1' THEN 'high'
               WHEN 'P2' THEN 'medium'
               WHEN 'P3' THEN 'low'
           END
        """
    )
    op.alter_column(
        "risk_candidates",
        "cve_id",
        existing_type=sa.String(length=32),
        nullable=False,
        comment="Dependabot Alert Advisory와 연결할 CVE 식별자",
    )
    op.alter_column(
        "risk_candidates",
        "priority",
        existing_type=sa.String(length=20),
        comment="Gold가 부여한 고객 독립적 후보 우선순위",
    )
    op.create_check_constraint(
        op.f("ck_risk_candidates_priority_values"),
        "risk_candidates",
        "priority IN ('low', 'medium', 'high', 'critical')",
    )
    op.create_table_comment(
        "risk_candidates",
        "Gold가 선정한 CVE 기준 위험 변화 후보",
        existing_comment="Gold가 선정한 CVE 또는 GHSA 기준 위험 변화 후보",
    )

    op.drop_column("gold_batches", "ds_run_id")
