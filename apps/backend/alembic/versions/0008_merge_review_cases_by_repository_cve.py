"""merge review cases by repository and CVE

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            CREATE TEMP TABLE review_case_merge_map ON COMMIT DROP AS
            WITH ranked AS (
                SELECT rc.id AS case_id,
                       first_value(rc.id) OVER (
                           PARTITION BY rc.organization_id, da.repository_id, sa.cve_id
                           ORDER BY candidate.selected_at DESC, rc.id
                       ) AS keeper_id,
                       count(*) OVER (
                           PARTITION BY rc.organization_id, da.repository_id, sa.cve_id
                       ) AS case_count
                  FROM review_cases rc
                  JOIN dependabot_alerts da ON da.id = rc.alert_id
                  JOIN security_advisories sa ON sa.id = da.advisory_id
                  JOIN risk_candidates candidate
                    ON candidate.id = rc.representative_candidate_id
                 WHERE sa.cve_id IS NOT NULL
            )
            SELECT case_id, keeper_id
              FROM ranked
             WHERE case_count > 1;

            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                      FROM review_activities activity
                      JOIN review_case_merge_map merge_map
                        ON merge_map.case_id = activity.review_case_id
                     WHERE merge_map.case_id <> merge_map.keeper_id
                       AND activity.activity_type NOT IN (
                           'case_opened', 'case_reopened', 'case_resolved'
                       )
                ) OR EXISTS (
                    SELECT 1
                      FROM external_links link
                      JOIN review_case_merge_map merge_map
                        ON merge_map.case_id = link.review_case_id
                     WHERE merge_map.case_id <> merge_map.keeper_id
                ) THEN
                    RAISE EXCEPTION
                        '사용자 활동 또는 외부 링크가 있는 중복 Case는 자동 병합할 수 없습니다.';
                END IF;
            END
            $$;

            DELETE FROM review_activities activity
             USING review_case_merge_map merge_map
             WHERE activity.review_case_id = merge_map.case_id
               AND merge_map.case_id <> merge_map.keeper_id;

            DELETE FROM review_cases review_case
             USING review_case_merge_map merge_map
             WHERE review_case.id = merge_map.case_id
               AND merge_map.case_id <> merge_map.keeper_id;
            """
        )
    )
    op.create_table_comment(
        "review_cases",
        "같은 저장소와 CVE에 연결된 Alert들의 재검토 수명 주기",
        existing_comment="Dependabot Alert 한 건의 재검토 수명 주기",
    )
    op.alter_column(
        "review_cases",
        "alert_id",
        existing_type=sa.Uuid(),
        existing_nullable=False,
        comment="Case의 대표 Dependabot Alert 식별자",
    )


def downgrade() -> None:
    op.alter_column(
        "review_cases",
        "alert_id",
        existing_type=sa.Uuid(),
        existing_nullable=False,
        comment="Case가 검토하는 Dependabot Alert 식별자",
    )
    op.create_table_comment(
        "review_cases",
        "Dependabot Alert 한 건의 재검토 수명 주기",
        existing_comment="같은 저장소와 CVE에 연결된 Alert들의 재검토 수명 주기",
    )
