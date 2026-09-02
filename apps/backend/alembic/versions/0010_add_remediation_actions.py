"""add remediation actions and immutable targets

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "remediation_actions",
        sa.Column("id", sa.Uuid(), nullable=False, comment="패키지 조치 내부 식별자"),
        sa.Column(
            "organization_id",
            sa.Uuid(),
            nullable=False,
            comment="조치가 속한 조직 식별자",
        ),
        sa.Column(
            "actor_user_id",
            sa.Uuid(),
            nullable=False,
            comment="조치를 기록한 사용자 식별자",
        ),
        sa.Column(
            "group_key",
            sa.String(length=64),
            nullable=False,
            comment="조직·ecosystem·패키지로 계산한 조치 그룹 키",
        ),
        sa.Column(
            "ecosystem",
            sa.String(length=50),
            nullable=False,
            comment="조치 대상 패키지 생태계",
        ),
        sa.Column(
            "package_name",
            sa.String(length=255),
            nullable=False,
            comment="조치 대상 패키지 이름",
        ),
        sa.Column(
            "action_type",
            sa.String(length=30),
            nullable=False,
            comment="위험 수용 또는 조치 요청 유형",
        ),
        sa.Column(
            "watchback_state",
            sa.String(length=30),
            nullable=False,
            comment="GitHub 상태와 분리한 Watchback 조치 상태",
        ),
        sa.Column(
            "target_fingerprint",
            sa.String(length=64),
            nullable=False,
            comment="조치 시점 대상 집합의 SHA-256",
        ),
        sa.Column(
            "note",
            sa.Text(),
            nullable=False,
            comment="사용자가 남긴 조치 판단 근거",
        ),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="사용자가 조치를 기록한 시각",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="운영 DB에 패키지 조치를 생성한 시각",
        ),
        sa.CheckConstraint(
            "action_type IN ('risk_accepted', 'remediation_requested')",
            name=op.f("ck_remediation_actions_action_type_values"),
        ),
        sa.CheckConstraint(
            "(action_type = 'risk_accepted' AND watchback_state = 'accepted') OR "
            "(action_type = 'remediation_requested' AND watchback_state IN ("
            "'requested', 'pr_open', 'pr_merged', 'verification_pending', "
            "'completed', 'failed'))",
            name=op.f("ck_remediation_actions_type_state_consistency"),
        ),
        sa.CheckConstraint(
            "watchback_state IN ('accepted', 'requested', 'pr_open', 'pr_merged', "
            "'verification_pending', 'completed', 'failed')",
            name=op.f("ck_remediation_actions_watchback_state_values"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "actor_user_id"],
            ["users.organization_id", "users.id"],
            name=op.f(
                "fk_remediation_actions_organization_id_actor_user_id_users"
            ),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_remediation_actions")),
        sa.UniqueConstraint(
            "organization_id",
            "group_key",
            "action_type",
            "target_fingerprint",
            name=op.f(
                "uq_remediation_actions_organization_id_group_key_action_type_target_fingerprint"
            ),
        ),
        sa.UniqueConstraint(
            "organization_id",
            "id",
            name=op.f("uq_remediation_actions_organization_id_id"),
        ),
        comment="패키지 조치 그룹에 사용자가 기록한 Watchback 조치",
    )
    op.create_index(
        "ix_remediation_actions_organization_package_occurred",
        "remediation_actions",
        ["organization_id", "ecosystem", "package_name", "occurred_at"],
        unique=False,
    )

    op.create_table(
        "remediation_action_targets",
        sa.Column("id", sa.Uuid(), nullable=False, comment="조치 대상 Snapshot 내부 식별자"),
        sa.Column(
            "organization_id",
            sa.Uuid(),
            nullable=False,
            comment="조치 대상이 속한 조직 식별자",
        ),
        sa.Column(
            "action_id",
            sa.Uuid(),
            nullable=False,
            comment="대상을 고정한 패키지 조치 식별자",
        ),
        sa.Column(
            "review_case_id",
            sa.Uuid(),
            nullable=False,
            comment="조치 시점의 재검토 Case 식별자",
        ),
        sa.Column(
            "candidate_id",
            sa.Uuid(),
            nullable=False,
            comment="조치 시점 Case의 대표 Candidate 식별자",
        ),
        sa.Column(
            "alert_id",
            sa.Uuid(),
            nullable=False,
            comment="조치 시점의 Open Dependabot Alert 식별자",
        ),
        sa.Column(
            "repository_id",
            sa.Uuid(),
            nullable=False,
            comment="조치 시점 Alert 저장소 식별자",
        ),
        sa.Column(
            "repository_full_name",
            sa.String(length=255),
            nullable=False,
            comment="조치 시점 저장소 전체 이름",
        ),
        sa.Column(
            "manifest_path",
            sa.String(length=500),
            nullable=True,
            comment="조치 시점 Alert manifest 경로",
        ),
        sa.Column(
            "github_alert_number",
            sa.Integer(),
            nullable=False,
            comment="조치 시점 GitHub Alert 번호",
        ),
        sa.Column(
            "github_alert_state_at_action",
            sa.String(length=20),
            nullable=False,
            comment="조치 시점에 관찰한 GitHub Alert 상태",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="운영 DB에 조치 대상을 생성한 시각",
        ),
        sa.CheckConstraint(
            "github_alert_state_at_action IN "
            "('open', 'dismissed', 'fixed', 'auto_dismissed')",
            name=op.f(
                "ck_remediation_action_targets_github_alert_state_values"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "action_id"],
            ["remediation_actions.organization_id", "remediation_actions.id"],
            name=op.f(
                "fk_remediation_action_targets_organization_id_action_id_remediation_actions"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "alert_id"],
            ["dependabot_alerts.organization_id", "dependabot_alerts.id"],
            name=op.f(
                "fk_remediation_action_targets_organization_id_alert_id_dependabot_alerts"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["risk_candidates.id"],
            name=op.f(
                "fk_remediation_action_targets_candidate_id_risk_candidates"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "repository_id"],
            ["repositories.organization_id", "repositories.id"],
            name=op.f(
                "fk_remediation_action_targets_organization_id_repository_id_repositories"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "review_case_id"],
            ["review_cases.organization_id", "review_cases.id"],
            name=op.f(
                "fk_remediation_action_targets_organization_id_review_case_id_review_cases"
            ),
        ),
        sa.PrimaryKeyConstraint(
            "id", name=op.f("pk_remediation_action_targets")
        ),
        sa.UniqueConstraint(
            "action_id",
            "review_case_id",
            "candidate_id",
            "alert_id",
            name=op.f(
                "uq_remediation_action_targets_action_id_review_case_id_candidate_id_alert_id"
            ),
        ),
        comment="패키지 조치 시점에 고정한 Case·Candidate·Alert 대상",
    )
    op.create_index(
        "ix_remediation_action_targets_action_id",
        "remediation_action_targets",
        ["action_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_remediation_action_targets_action_id",
        table_name="remediation_action_targets",
    )
    op.drop_table("remediation_action_targets")
    op.drop_index(
        "ix_remediation_actions_organization_package_occurred",
        table_name="remediation_actions",
    )
    op.drop_table("remediation_actions")
