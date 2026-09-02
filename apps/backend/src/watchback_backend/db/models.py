from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class IdMixin:
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)


class CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class TimestampMixin(CreatedAtMixin):
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class Organization(IdMixin, TimestampMixin, Base):
    __tablename__ = "organizations"
    __table_args__ = {"comment": "GitHub 조직 단위 테넌트"}

    github_organization_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, unique=True
    )
    github_login: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)


class User(IdMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("organization_id", "id"),
        UniqueConstraint("organization_id", "email"),
        {"comment": "조직에 소속된 사용자"},
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    github_user_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_demo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )


class Repository(IdMixin, TimestampMixin, Base):
    __tablename__ = "repositories"
    __table_args__ = (
        UniqueConstraint("organization_id", "id"),
        UniqueConstraint("organization_id", "github_repository_id"),
        CheckConstraint(
            "importance IN ('low', 'medium', 'high', 'critical')",
            name="importance_values",
        ),
        {"comment": "조직이 관리하는 GitHub 저장소"},
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    github_repository_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    default_branch: Mapped[str | None] = mapped_column(String(255))
    importance: Mapped[str] = mapped_column(String(20), nullable=False)
    github_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class SecurityAdvisory(IdMixin, TimestampMixin, Base):
    __tablename__ = "security_advisories"
    __table_args__ = (
        CheckConstraint(
            "severity IN ('low', 'medium', 'high', 'critical')",
            name="severity_values",
        ),
        CheckConstraint("cvss_score BETWEEN 0 AND 10", name="cvss_score_range"),
        {"comment": "GHSA 기준 공용 보안 권고 메타데이터"},
    )

    ghsa_id: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    cve_id: Mapped[str | None] = mapped_column(String(32), index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    cvss_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    github_published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    github_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    github_withdrawn_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )


class DependabotAlert(IdMixin, TimestampMixin, Base):
    __tablename__ = "dependabot_alerts"
    __table_args__ = (
        UniqueConstraint("organization_id", "id"),
        UniqueConstraint("repository_id", "github_alert_number"),
        ForeignKeyConstraint(
            ["organization_id", "repository_id"],
            ["repositories.organization_id", "repositories.id"],
        ),
        CheckConstraint(
            "state IN ('open', 'dismissed', 'fixed', 'auto_dismissed')",
            name="state_values",
        ),
        CheckConstraint(
            "dependency_scope IS NULL OR dependency_scope IN ('runtime', 'development')",
            name="dependency_scope_values",
        ),
        CheckConstraint(
            "dependency_relationship IS NULL OR "
            "dependency_relationship IN ('direct', 'transitive', 'unknown')",
            name="dependency_relationship_values",
        ),
        CheckConstraint(
            "(state = 'open' AND dismissed_at IS NULL AND fixed_at IS NULL "
            "AND auto_dismissed_at IS NULL) OR "
            "(state = 'dismissed' AND dismissed_at IS NOT NULL) OR "
            "(state = 'fixed' AND fixed_at IS NOT NULL) OR "
            "(state = 'auto_dismissed' AND auto_dismissed_at IS NOT NULL)",
            name="state_timestamp_consistency",
        ),
        Index("ix_dependabot_alerts_organization_state", "organization_id", "state"),
        Index(
            "ix_dependabot_alerts_organization_package",
            "organization_id",
            "package_name",
        ),
        Index("ix_dependabot_alerts_advisory_id", "advisory_id"),
        Index("ix_dependabot_alerts_github_updated_at", "github_updated_at"),
        {"comment": "GitHub Dependabot Alert의 현재 상태"},
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    repository_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    advisory_id: Mapped[UUID] = mapped_column(
        ForeignKey("security_advisories.id"), nullable=False
    )
    github_alert_number: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False)
    package_name: Mapped[str] = mapped_column(String(255), nullable=False)
    ecosystem: Mapped[str] = mapped_column(String(50), nullable=False)
    manifest_path: Mapped[str | None] = mapped_column(String(500))
    dependency_scope: Mapped[str | None] = mapped_column(String(30))
    dependency_relationship: Mapped[str | None] = mapped_column(String(30))
    vulnerable_version_range: Mapped[str] = mapped_column(String(255), nullable=False)
    first_patched_version: Mapped[str | None] = mapped_column(String(100))
    html_url: Mapped[str] = mapped_column(Text, nullable=False)
    github_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    github_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dismissed_reason: Mapped[str | None] = mapped_column(String(255))
    dismissed_by: Mapped[str | None] = mapped_column(String(255))
    dismissed_comment: Mapped[str | None] = mapped_column(Text)
    fixed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    auto_dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class DependencyVersionSnapshot(IdMixin, TimestampMixin, Base):
    __tablename__ = "dependency_version_snapshots"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "repository_id"],
            ["repositories.organization_id", "repositories.id"],
        ),
        CheckConstraint(
            "status IN ('resolved', 'multiple', 'unavailable', 'invalid')",
            name="status_values",
        ),
        CheckConstraint(
            "reason IS NULL OR reason IN ("
            "'unsupported_manifest', 'lockfile_not_found', "
            "'package_not_found', 'invalid_lockfile')",
            name="reason_values",
        ),
        CheckConstraint(
            "jsonb_typeof(resolved_versions) = 'array'",
            name="resolved_versions_array",
        ),
        CheckConstraint(
            "(status = 'resolved' AND jsonb_array_length(resolved_versions) = 1 "
            "AND reason IS NULL) OR "
            "(status = 'multiple' AND jsonb_array_length(resolved_versions) > 1 "
            "AND reason IS NULL) OR "
            "(status = 'unavailable' AND jsonb_array_length(resolved_versions) = 0 "
            "AND reason IN ('unsupported_manifest', 'lockfile_not_found', "
            "'package_not_found')) OR "
            "(status = 'invalid' AND jsonb_array_length(resolved_versions) = 0 "
            "AND reason = 'invalid_lockfile')",
            name="resolution_consistency",
        ),
        Index(
            "uq_dependency_version_snapshots_identity",
            "repository_id",
            "manifest_path",
            "commit_sha",
            "ecosystem",
            "package_name",
            unique=True,
            postgresql_nulls_not_distinct=True,
        ),
        Index(
            "ix_dependency_version_snapshots_repository_observed",
            "repository_id",
            "observed_at",
        ),
        {"comment": "저장소 commit 기준 의존성 실제 사용 버전 수집 결과"},
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    repository_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    manifest_path: Mapped[str | None] = mapped_column(String(500))
    commit_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    ecosystem: Mapped[str] = mapped_column(String(50), nullable=False)
    package_name: Mapped[str] = mapped_column(String(255), nullable=False)
    resolved_versions: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(50))
    source_path: Mapped[str | None] = mapped_column(String(500))
    source_blob_sha: Mapped[str | None] = mapped_column(String(64))
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class RemediationAction(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "remediation_actions"
    __table_args__ = (
        UniqueConstraint("organization_id", "id"),
        ForeignKeyConstraint(
            ["organization_id", "actor_user_id"],
            ["users.organization_id", "users.id"],
        ),
        ForeignKeyConstraint(
            ["organization_id", "revoked_by_user_id"],
            ["users.organization_id", "users.id"],
        ),
        CheckConstraint(
            "action_type IN ('risk_accepted', 'remediation_requested')",
            name="action_type_values",
        ),
        CheckConstraint(
            "watchback_state IN ('accepted', 'requested', 'pr_open', 'pr_merged', "
            "'verification_pending', 'completed', 'cancelled', 'failed')",
            name="watchback_state_values",
        ),
        CheckConstraint(
            "(action_type = 'risk_accepted' AND watchback_state = 'accepted') OR "
            "(action_type = 'remediation_requested' AND watchback_state IN ("
            "'requested', 'pr_open', 'pr_merged', 'verification_pending', "
            "'completed', 'cancelled', 'failed'))",
            name="type_state_consistency",
        ),
        CheckConstraint(
            "reason_code IS NULL OR reason_code IN "
            "('compatibility_blocked', 'low_current_impact', 'other')",
            name="reason_code_values",
        ),
        CheckConstraint(
            "(action_type = 'risk_accepted' AND reason_code IS NOT NULL) OR "
            "(action_type = 'remediation_requested' AND reason_code IS NULL)",
            name="risk_reason_required",
        ),
        CheckConstraint(
            "reason_code <> 'other' OR "
            "(note IS NOT NULL AND length(trim(note)) > 0)",
            name="other_note_required",
        ),
        CheckConstraint(
            "(revoked_at IS NULL AND revoked_by_user_id IS NULL) OR "
            "(revoked_at IS NOT NULL AND revoked_by_user_id IS NOT NULL)",
            name="revocation_consistency",
        ),
        Index(
            "uq_remediation_actions_active_target_fingerprint",
            "organization_id",
            "group_key",
            "action_type",
            "target_fingerprint",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
        ),
        Index(
            "ix_remediation_actions_organization_package_occurred",
            "organization_id",
            "ecosystem",
            "package_name",
            "occurred_at",
        ),
        {"comment": "패키지 조치 그룹에 사용자가 기록한 Watchback 조치"},
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    actor_user_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    group_key: Mapped[str] = mapped_column(String(64), nullable=False)
    ecosystem: Mapped[str] = mapped_column(String(50), nullable=False)
    package_name: Mapped[str] = mapped_column(String(255), nullable=False)
    action_type: Mapped[str] = mapped_column(String(30), nullable=False)
    watchback_state: Mapped[str] = mapped_column(String(30), nullable=False)
    target_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    reason_code: Mapped[str | None] = mapped_column(
        String(40), comment="위험 수용의 구조화된 사유 코드"
    )
    note: Mapped[str | None] = mapped_column(
        Text, comment="위험 수용 기타 사유 또는 조치 요청 메모"
    )
    result: Mapped[dict | None] = mapped_column(
        JSONB, comment="자동조치 실행 결과와 생성된 GitHub PR 정보"
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), comment="위험 수용을 취소하고 재검토를 연 시각"
    )
    revoked_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid, comment="위험 수용을 취소한 사용자 식별자"
    )
    revocation_note: Mapped[str | None] = mapped_column(
        Text, comment="위험 수용 취소 시 남긴 선택 메모"
    )


class RemediationActionTarget(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "remediation_action_targets"
    __table_args__ = (
        UniqueConstraint(
            "action_id",
            "review_case_id",
            "candidate_id",
            "alert_id",
        ),
        ForeignKeyConstraint(
            ["organization_id", "action_id"],
            ["remediation_actions.organization_id", "remediation_actions.id"],
        ),
        ForeignKeyConstraint(
            ["organization_id", "revoked_by_user_id"],
            ["users.organization_id", "users.id"],
        ),
        CheckConstraint(
            "(revoked_at IS NULL AND revoked_by_user_id IS NULL) OR "
            "(revoked_at IS NOT NULL AND revoked_by_user_id IS NOT NULL)",
            name="revocation_consistency",
        ),
        ForeignKeyConstraint(
            ["organization_id", "review_case_id"],
            ["review_cases.organization_id", "review_cases.id"],
        ),
        ForeignKeyConstraint(
            ["organization_id", "alert_id"],
            ["dependabot_alerts.organization_id", "dependabot_alerts.id"],
        ),
        ForeignKeyConstraint(
            ["organization_id", "repository_id"],
            ["repositories.organization_id", "repositories.id"],
        ),
        CheckConstraint(
            "github_alert_state_at_action IN "
            "('open', 'dismissed', 'fixed', 'auto_dismissed')",
            name="github_alert_state_values",
        ),
        Index("ix_remediation_action_targets_action_id", "action_id"),
        {"comment": "패키지 조치 시점에 고정한 Case·Candidate·Alert 대상"},
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    action_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    review_case_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    candidate_id: Mapped[UUID] = mapped_column(
        ForeignKey("risk_candidates.id"), nullable=False
    )
    alert_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    repository_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    repository_full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    manifest_path: Mapped[str | None] = mapped_column(String(500))
    github_alert_number: Mapped[int] = mapped_column(Integer, nullable=False)
    github_alert_state_at_action: Mapped[str] = mapped_column(
        String(20), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), comment="개별 조치 대상의 위험 수용을 취소한 시각"
    )
    revoked_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid, comment="개별 조치 대상의 위험 수용을 취소한 사용자"
    )
    revocation_note: Mapped[str | None] = mapped_column(
        Text, comment="개별 조치 대상의 위험 수용 취소 메모"
    )


class RemediationAISummary(IdMixin, TimestampMixin, Base):
    __tablename__ = "remediation_ai_summaries"
    __table_args__ = (
        UniqueConstraint("organization_id", "group_key"),
        ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        Index(
            "ix_remediation_ai_summaries_organization_package",
            "organization_id",
            "ecosystem",
            "package_name",
        ),
        {"comment": "패키지 조치 그룹별로 일괄 생성해 영구 저장한 AI 요약"},
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    group_key: Mapped[str] = mapped_column(String(64), nullable=False)
    ecosystem: Mapped[str] = mapped_column(String(50), nullable=False)
    package_name: Mapped[str] = mapped_column(String(255), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(50), nullable=False)
    risk_summary: Mapped[str] = mapped_column(Text, nullable=False)
    action_summary: Mapped[str] = mapped_column(Text, nullable=False)
    interpretation_note: Mapped[str | None] = mapped_column(
        Text,
        comment="검토된 EPSS 모델·소스 변동과 겹치는 요약의 해석 주의 문구",
    )
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    source_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class AIContextDocument(IdMixin, TimestampMixin, Base):
    __tablename__ = "ai_context_documents"
    __table_args__ = (
        UniqueConstraint("organization_id", "group_key", "document_type"),
        ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        CheckConstraint(
            "document_type IN ('usage_indicators', 'upgrade_notes')",
            name="document_type_values",
        ),
        Index(
            "ix_ai_context_documents_organization_package",
            "organization_id",
            "ecosystem",
            "package_name",
        ),
        {"comment": "패키지 조치 판단을 위해 백필한 저장소 단서와 업데이트 정보"},
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    group_key: Mapped[str] = mapped_column(String(64), nullable=False)
    ecosystem: Mapped[str] = mapped_column(String(50), nullable=False)
    package_name: Mapped[str] = mapped_column(String(255), nullable=False)
    document_type: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    source_revision: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class GoldBatch(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "gold_batches"
    __table_args__ = (
        CheckConstraint("candidate_count >= 0", name="candidate_count_nonnegative"),
        {"comment": "완료된 Gold 위험 후보 전달 Batch"},
    )

    source_batch_id: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True
    )
    ds_run_id: Mapped[str | None] = mapped_column(String(255))
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(50), nullable=False)
    candidate_count: Mapped[int] = mapped_column(Integer, nullable=False)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RiskCandidate(IdMixin, TimestampMixin, Base):
    __tablename__ = "risk_candidates"
    __table_args__ = (
        CheckConstraint(
            "subject_type = 'CVE'",
            name="subject_type_values",
        ),
        CheckConstraint(
            "subject_type = 'CVE' AND subject_id = cve_id",
            name="subject_consistency",
        ),
        CheckConstraint(
            "priority IN ('P0', 'P1', 'P2', 'P3')",
            name="priority_values",
        ),
        {"comment": "Gold가 선정한 CVE 기준 위험 변화 후보"},
    )

    source_candidate_id: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True
    )
    subject_type: Mapped[str] = mapped_column(String(10), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    ghsa_id: Mapped[str | None] = mapped_column(String(40), index=True)
    cve_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    priority: Mapped[str] = mapped_column(String(20), nullable=False)
    change_type: Mapped[str] = mapped_column(String(100), nullable=False)
    reason_summary: Mapped[str] = mapped_column(Text, nullable=False)
    selected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class GoldBatchCandidate(Base):
    __tablename__ = "gold_batch_candidates"
    __table_args__ = {"comment": "Gold Batch별 위험 후보 전달 이력"}

    batch_id: Mapped[UUID] = mapped_column(
        ForeignKey("gold_batches.id"), primary_key=True
    )
    candidate_id: Mapped[UUID] = mapped_column(
        ForeignKey("risk_candidates.id"), primary_key=True
    )
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class CandidateEvidence(IdMixin, TimestampMixin, Base):
    __tablename__ = "candidate_evidence"
    __table_args__ = (
        CheckConstraint(
            "value_type IN ('boolean', 'decimal', 'version', 'timestamp', 'text')",
            name="value_type_values",
        ),
        UniqueConstraint("batch_id", "source_evidence_id"),
        ForeignKeyConstraint(
            ["batch_id", "candidate_id"],
            ["gold_batch_candidates.batch_id", "gold_batch_candidates.candidate_id"],
        ),
        Index(
            "ix_candidate_evidence_candidate_observed", "candidate_id", "observed_at"
        ),
        Index("ix_candidate_evidence_signal_observed", "signal", "observed_at"),
        {"comment": "위험 후보를 뒷받침하는 신호별 변화 전후 근거"},
    )

    source_evidence_id: Mapped[str] = mapped_column(String(255), nullable=False)
    batch_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    candidate_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    signal: Mapped[str] = mapped_column(String(100), nullable=False)
    value_type: Mapped[str] = mapped_column(String(20), nullable=False)
    previous_value: Mapped[str | None] = mapped_column(Text)
    current_value: Mapped[str | None] = mapped_column(Text)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    evidence_summary: Mapped[str] = mapped_column(Text, nullable=False)


class AlertCandidateMatch(Base):
    __tablename__ = "alert_candidate_matches"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "alert_id"],
            ["dependabot_alerts.organization_id", "dependabot_alerts.id"],
        ),
        {"comment": "Dependabot Alert와 Gold 위험 후보의 CVE 매칭 결과"},
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    alert_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    candidate_id: Mapped[UUID] = mapped_column(
        ForeignKey("risk_candidates.id"), primary_key=True
    )
    matched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class ReviewCase(IdMixin, TimestampMixin, Base):
    __tablename__ = "review_cases"
    __table_args__ = (
        UniqueConstraint("organization_id", "id"),
        ForeignKeyConstraint(
            ["organization_id", "alert_id"],
            ["dependabot_alerts.organization_id", "dependabot_alerts.id"],
        ),
        ForeignKeyConstraint(
            ["representative_batch_id", "representative_candidate_id"],
            ["gold_batch_candidates.batch_id", "gold_batch_candidates.candidate_id"],
        ),
        UniqueConstraint("alert_id"),
        CheckConstraint("status IN ('open', 'resolved')", name="status_values"),
        CheckConstraint(
            "priority IN ('low', 'medium', 'high', 'critical')",
            name="priority_values",
        ),
        CheckConstraint(
            "(status = 'open' AND resolved_at IS NULL) OR "
            "(status = 'resolved' AND resolved_at IS NOT NULL)",
            name="status_timestamp_consistency",
        ),
        CheckConstraint("reopened_count >= 0", name="reopened_count_nonnegative"),
        Index(
            "ix_review_cases_organization_status_priority",
            "organization_id",
            "status",
            "priority",
        ),
        Index(
            "ix_review_cases_organization_updated_at", "organization_id", "updated_at"
        ),
        {"comment": "같은 저장소와 CVE에 연결된 Alert들의 재검토 수명 주기"},
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    alert_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    representative_candidate_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    representative_batch_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    priority: Mapped[str] = mapped_column(String(20), nullable=False)
    review_reason: Mapped[str] = mapped_column(Text, nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_reopened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reopened_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )


class ReviewActivity(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "review_activities"
    __table_args__ = (
        UniqueConstraint("organization_id", "review_case_id", "id"),
        ForeignKeyConstraint(
            ["organization_id", "review_case_id"],
            ["review_cases.organization_id", "review_cases.id"],
        ),
        ForeignKeyConstraint(
            ["organization_id", "actor_user_id"],
            ["users.organization_id", "users.id"],
        ),
        UniqueConstraint("review_case_id", "candidate_id", "activity_type"),
        CheckConstraint(
            "activity_type IN ('case_opened', 'case_reopened', 'case_resolved', "
            "'review_deferred', 'risk_accepted', 'remediation_requested', "
            "'note_added', 'external_link_added')",
            name="activity_type_values",
        ),
        Index(
            "ix_review_activities_organization_case_occurred",
            "organization_id",
            "review_case_id",
            "occurred_at",
        ),
        {"comment": "추가 전용 재검토 Case 활동 이력"},
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    review_case_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    actor_user_id: Mapped[UUID | None] = mapped_column(Uuid)
    candidate_id: Mapped[UUID | None] = mapped_column(ForeignKey("risk_candidates.id"))
    activity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class ExternalLink(IdMixin, TimestampMixin, Base):
    __tablename__ = "external_links"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "review_case_id"],
            ["review_cases.organization_id", "review_cases.id"],
        ),
        ForeignKeyConstraint(
            ["organization_id", "review_case_id", "created_by_activity_id"],
            [
                "review_activities.organization_id",
                "review_activities.review_case_id",
                "review_activities.id",
            ],
        ),
        UniqueConstraint("organization_id", "url"),
        CheckConstraint(
            "link_type IN ('issue', 'pull_request')", name="link_type_values"
        ),
        {"comment": "재검토 Case에 연결된 GitHub Issue 또는 Pull Request"},
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    review_case_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    created_by_activity_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    link_type: Mapped[str] = mapped_column(String(30), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    github_owner: Mapped[str] = mapped_column(String(255), nullable=False)
    github_repository: Mapped[str] = mapped_column(String(255), nullable=False)
    github_number: Mapped[int] = mapped_column(Integer, nullable=False)
    external_state: Mapped[str | None] = mapped_column(String(30))
    github_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


COLUMN_COMMENTS: dict[str, dict[str, str]] = {
    "organizations": {
        "id": "조직 내부 식별자",
        "github_organization_id": "GitHub가 발급한 조직 식별자",
        "github_login": "GitHub 조직 로그인 이름",
        "display_name": "화면에 표시할 조직 이름",
        "created_at": "운영 DB에 조직을 생성한 시각",
        "updated_at": "운영 DB에서 조직을 마지막으로 수정한 시각",
    },
    "users": {
        "id": "사용자 내부 식별자",
        "organization_id": "사용자가 소속된 조직 식별자",
        "github_user_id": "GitHub가 발급한 사용자 식별자",
        "email": "조직 내 사용자 이메일",
        "display_name": "화면에 표시할 사용자 이름",
        "is_demo": "시연용 사용자 여부",
        "created_at": "운영 DB에 사용자를 생성한 시각",
        "updated_at": "운영 DB에서 사용자를 마지막으로 수정한 시각",
    },
    "repositories": {
        "id": "저장소 내부 식별자",
        "organization_id": "저장소를 소유한 조직 식별자",
        "github_repository_id": "GitHub가 발급한 저장소 식별자",
        "full_name": "owner/repository 형식의 GitHub 저장소 전체 이름",
        "display_name": "화면에 표시할 가상 회사 기준 저장소 이름",
        "default_branch": "GitHub 저장소 기본 브랜치 이름",
        "importance": "조직이 지정한 저장소 중요도",
        "github_updated_at": "GitHub에서 저장소가 마지막으로 변경된 시각",
        "last_synced_at": "GitHub 저장소 정보를 마지막으로 동기화한 시각",
        "created_at": "운영 DB에 저장소를 생성한 시각",
        "updated_at": "운영 DB에서 저장소를 마지막으로 수정한 시각",
    },
    "security_advisories": {
        "id": "보안 권고 내부 식별자",
        "ghsa_id": "GitHub Security Advisory 식별자",
        "cve_id": "연결된 CVE 식별자이며 CVE가 없으면 null",
        "summary": "GitHub 보안 권고 요약",
        "description": "GitHub 보안 권고 상세 설명",
        "severity": "GitHub 보안 권고 심각도",
        "cvss_score": "CVSS 기본 점수",
        "github_published_at": "GitHub가 보안 권고를 최초 공개한 시각",
        "github_updated_at": "GitHub가 보안 권고를 마지막으로 수정한 시각",
        "github_withdrawn_at": "GitHub가 보안 권고를 철회한 시각",
        "created_at": "운영 DB에 보안 권고를 생성한 시각",
        "updated_at": "운영 DB에서 보안 권고를 마지막으로 수정한 시각",
    },
    "dependabot_alerts": {
        "id": "Dependabot Alert 내부 식별자",
        "organization_id": "Alert가 속한 조직 식별자",
        "repository_id": "Alert가 발생한 저장소 식별자",
        "advisory_id": "Alert가 참조하는 보안 권고 식별자",
        "github_alert_number": "저장소 안에서 GitHub가 부여한 Alert 번호",
        "state": "Alert의 현재 상태",
        "package_name": "취약한 의존성 패키지 이름",
        "ecosystem": "패키지 생태계 이름",
        "manifest_path": "취약한 의존성을 선언한 manifest 파일 경로",
        "dependency_scope": "의존성 사용 범위",
        "dependency_relationship": "직접 또는 간접 의존성 관계",
        "vulnerable_version_range": "취약점의 영향 버전 범위",
        "first_patched_version": "취약점이 처음 수정된 버전",
        "html_url": "GitHub Dependabot Alert 화면 URL",
        "github_created_at": "GitHub가 Alert를 생성한 시각",
        "github_updated_at": "GitHub가 Alert를 마지막으로 수정한 시각",
        "dismissed_at": "GitHub에서 Alert를 기각한 시각",
        "dismissed_reason": "GitHub Alert 기각 사유 코드",
        "dismissed_by": "GitHub에서 Alert를 기각한 사용자",
        "dismissed_comment": "GitHub Alert 기각 설명",
        "fixed_at": "GitHub에서 Alert가 수정 완료된 시각",
        "auto_dismissed_at": "GitHub가 Alert를 자동 기각한 시각",
        "last_synced_at": "GitHub Alert를 마지막으로 동기화한 시각",
        "created_at": "운영 DB에 Alert를 생성한 시각",
        "updated_at": "운영 DB에서 Alert를 마지막으로 수정한 시각",
    },
    "dependency_version_snapshots": {
        "id": "실제 사용 버전 Snapshot 내부 식별자",
        "organization_id": "Snapshot이 속한 조직 식별자",
        "repository_id": "버전을 수집한 저장소 식별자",
        "manifest_path": "Dependabot Alert가 가리킨 manifest 경로",
        "commit_sha": "파일을 조회한 저장소 commit SHA",
        "ecosystem": "패키지 생태계 이름",
        "package_name": "실제 버전을 확인한 패키지 이름",
        "resolved_versions": "lockfile에서 확인한 실제 사용 버전 목록",
        "status": "단일·복수 버전 확인 또는 확인 불가 상태",
        "reason": "확인 불가 또는 파싱 실패의 상세 사유",
        "source_path": "실제 버전을 읽은 lockfile 경로",
        "source_blob_sha": "실제 버전을 읽은 Git blob SHA",
        "observed_at": "GitHub에서 실제 버전을 수집한 시각",
        "created_at": "운영 DB에 Snapshot을 생성한 시각",
        "updated_at": "운영 DB에서 Snapshot을 마지막으로 수정한 시각",
    },
    "remediation_actions": {
        "id": "패키지 조치 내부 식별자",
        "organization_id": "조치가 속한 조직 식별자",
        "actor_user_id": "조치를 기록한 사용자 식별자",
        "group_key": "조직·ecosystem·패키지로 계산한 조치 그룹 키",
        "ecosystem": "조치 대상 패키지 생태계",
        "package_name": "조치 대상 패키지 이름",
        "action_type": "위험 수용 또는 조치 요청 유형",
        "watchback_state": "GitHub 상태와 분리한 Watchback 조치 상태",
        "target_fingerprint": "조치 시점 대상 집합의 SHA-256",
        "note": "사용자가 남긴 조치 판단 근거",
        "result": "자동조치 실행 결과와 생성된 GitHub PR 정보",
        "occurred_at": "사용자가 조치를 기록한 시각",
        "created_at": "운영 DB에 패키지 조치를 생성한 시각",
    },
    "remediation_action_targets": {
        "id": "조치 대상 Snapshot 내부 식별자",
        "organization_id": "조치 대상이 속한 조직 식별자",
        "action_id": "대상을 고정한 패키지 조치 식별자",
        "review_case_id": "조치 시점의 재검토 Case 식별자",
        "candidate_id": "조치 시점 Case의 대표 Candidate 식별자",
        "alert_id": "조치 시점의 Open Dependabot Alert 식별자",
        "repository_id": "조치 시점 Alert 저장소 식별자",
        "repository_full_name": "조치 시점 저장소 전체 이름",
        "manifest_path": "조치 시점 Alert manifest 경로",
        "github_alert_number": "조치 시점 GitHub Alert 번호",
        "github_alert_state_at_action": "조치 시점에 관찰한 GitHub Alert 상태",
        "created_at": "운영 DB에 조치 대상을 생성한 시각",
    },
    "remediation_ai_summaries": {
        "id": "AI 요약 내부 식별자",
        "organization_id": "AI 요약이 속한 조직 식별자",
        "group_key": "조직·ecosystem·패키지로 계산한 조치 그룹 키",
        "ecosystem": "요약 대상 패키지 생태계",
        "package_name": "요약 대상 패키지 이름",
        "prompt_version": "요약 생성에 사용한 프롬프트 버전",
        "risk_summary": "사용자에게 표시할 핵심 위험 요약",
        "action_summary": "사용자에게 표시할 권장 조치 요약",
        "model": "요약 생성에 사용한 Azure OpenAI 배포 모델",
        "source_ids": "요약 생성에 사용한 Watchback 근거 식별자 목록",
        "generated_at": "AI 요약을 생성한 시각",
        "created_at": "운영 DB에 AI 요약을 최초 저장한 시각",
        "updated_at": "운영 DB에서 AI 요약을 마지막으로 갱신한 시각",
    },
    "ai_context_documents": {
        "id": "AI 분석 문서 내부 식별자",
        "organization_id": "AI 분석 문서가 속한 조직 식별자",
        "group_key": "조직·ecosystem·패키지로 계산한 조치 그룹 키",
        "ecosystem": "분석 대상 패키지 생태계",
        "package_name": "분석 대상 패키지 이름",
        "document_type": "저장소 사용 단서 또는 업데이트 변경 정보 구분",
        "content": "근거와 한계를 보존한 구조화 분석 결과",
        "source_revision": "분석에 사용한 저장소 commit 또는 패키지 버전 식별자",
        "source_url": "공식 원문 또는 릴리스 정보 URL",
        "generated_at": "분석 문서를 생성한 시각",
        "created_at": "운영 DB에 분석 문서를 최초 저장한 시각",
        "updated_at": "운영 DB에서 분석 문서를 마지막으로 갱신한 시각",
    },
    "gold_batches": {
        "id": "Gold Batch 내부 식별자",
        "source_batch_id": "Gold가 발급한 외부 Batch 식별자",
        "ds_run_id": "DS 실행을 추적하는 선택적 식별자",
        "as_of": "후보 선정 결과가 유효한 기준 시각",
        "source_generated_at": "Gold가 Batch 결과를 생성한 시각",
        "policy_version": "후보 선정에 사용한 정책 버전",
        "schema_version": "Gold 전달 스키마 버전",
        "candidate_count": "Batch에 포함된 고유 Candidate 수",
        "synced_at": "Backend가 Batch를 동기화한 시각",
        "created_at": "운영 DB에 Batch를 생성한 시각",
    },
    "risk_candidates": {
        "id": "위험 후보 내부 식별자",
        "source_candidate_id": "Gold가 발급한 외부 위험 후보 식별자",
        "subject_type": "Alert 연결 기준 종류이며 S1에서는 CVE",
        "subject_id": "CVE 기준 공통 연결 식별자",
        "ghsa_id": "Gold 원본 GHSA 보조 식별자이며 없으면 null",
        "cve_id": "Alert 연결에 사용하는 필수 CVE 식별자",
        "priority": "Gold가 부여한 P0~P3 후보 우선순위",
        "change_type": "후보로 선정된 위험 변화 유형",
        "reason_summary": "후보 선정 사유 요약",
        "selected_at": "Gold가 위험 변화를 후보로 선정한 시각",
        "created_at": "운영 DB에 위험 후보를 생성한 시각",
        "updated_at": "운영 DB에서 위험 후보를 마지막으로 수정한 시각",
    },
    "gold_batch_candidates": {
        "batch_id": "위험 후보를 전달한 Gold Batch 식별자",
        "candidate_id": "Batch에 포함된 위험 후보 식별자",
        "payload_hash": "Candidate와 연결된 Evidence 집합을 정규화한 payload의 SHA-256 해시",
        "received_at": "Backend가 Batch 안의 후보를 수신한 시각",
    },
    "candidate_evidence": {
        "id": "후보 근거 내부 식별자",
        "source_evidence_id": "Gold가 발급한 외부 근거 식별자",
        "batch_id": "Evidence가 포함된 Gold Batch 식별자",
        "candidate_id": "근거가 뒷받침하는 위험 후보 식별자",
        "signal": "변화를 관찰한 위험 신호 이름",
        "value_type": "변화 전후 값을 해석할 자료형",
        "previous_value": "변화 전 값이며 이전 상태가 없으면 null",
        "current_value": "변화 후 값",
        "observed_at": "근거 신호의 변화를 관찰한 시각",
        "source": "근거 신호의 원천 데이터 이름",
        "evidence_summary": "Web 상세 화면에 표시할 근거 설명",
        "created_at": "운영 DB에 후보 근거를 생성한 시각",
        "updated_at": "운영 DB에서 후보 근거를 마지막으로 수정한 시각",
    },
    "alert_candidate_matches": {
        "organization_id": "Alert가 속한 조직 식별자",
        "alert_id": "매칭된 Dependabot Alert 식별자",
        "candidate_id": "매칭된 위험 후보 식별자",
        "matched_at": "Alert와 후보를 매칭한 시각",
    },
    "review_cases": {
        "id": "재검토 Case 내부 식별자",
        "organization_id": "Case가 속한 조직 식별자",
        "alert_id": "Case의 대표 Dependabot Alert 식별자",
        "representative_candidate_id": "Case 목록과 상단 요약에 사용하는 대표 Candidate 식별자",
        "representative_batch_id": "대표 Candidate를 전달한 Gold Batch 식별자",
        "status": "Case의 현재 검토 상태",
        "priority": "Web 화면에 표시할 Case 우선순위",
        "review_reason": "현재 대표 재검토 사유의 스냅샷",
        "opened_at": "Case를 최초로 연 시각",
        "resolved_at": "Case를 해결 완료한 시각",
        "last_reopened_at": "새 후보로 Case를 마지막으로 재오픈한 시각",
        "reopened_count": "Case가 재오픈된 누적 횟수",
        "created_at": "운영 DB에 Case를 생성한 시각",
        "updated_at": "운영 DB에서 Case를 마지막으로 수정한 시각",
    },
    "review_activities": {
        "id": "검토 활동 내부 식별자",
        "organization_id": "검토 활동이 속한 조직 식별자",
        "review_case_id": "활동이 기록된 재검토 Case 식별자",
        "actor_user_id": "활동을 수행한 사용자이며 시스템 활동이면 null",
        "candidate_id": "활동을 유발한 위험 후보 식별자",
        "activity_type": "Case 상태 변경 또는 사용자 조치 유형",
        "note": "검토 활동에 덧붙인 설명",
        "occurred_at": "활동이 실제로 발생한 시각",
        "created_at": "운영 DB에 활동 이력을 생성한 시각",
    },
    "external_links": {
        "id": "외부 링크 내부 식별자",
        "organization_id": "외부 링크가 속한 조직 식별자",
        "review_case_id": "외부 링크가 연결된 재검토 Case 식별자",
        "created_by_activity_id": "외부 링크 생성을 기록한 검토 활동 식별자",
        "link_type": "GitHub Issue 또는 Pull Request 구분",
        "url": "연결된 GitHub Issue 또는 Pull Request URL",
        "github_owner": "연결된 GitHub 저장소 소유자",
        "github_repository": "연결된 GitHub 저장소 이름",
        "github_number": "GitHub Issue 또는 Pull Request 번호",
        "external_state": "GitHub에서 확인한 외부 대상의 현재 상태",
        "github_updated_at": "GitHub에서 외부 대상이 마지막으로 변경된 시각",
        "last_synced_at": "외부 대상 상태를 마지막으로 동기화한 시각",
        "created_at": "운영 DB에 외부 링크를 생성한 시각",
        "updated_at": "운영 DB에서 외부 링크를 마지막으로 수정한 시각",
    },
}


for table_name, comments in COLUMN_COMMENTS.items():
    table = Base.metadata.tables[table_name]
    for column_name, comment in comments.items():
        table.columns[column_name].comment = comment
