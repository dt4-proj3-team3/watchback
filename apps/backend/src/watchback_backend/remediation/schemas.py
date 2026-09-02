from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from watchback_backend.api.schemas import (
    AdvisorySeverity,
    AlertState,
    CandidateDelivery,
    CandidateDetail,
    CandidatePriority,
    EvidenceResponse,
    Priority,
)


class RemediationContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class WatchbackGroupStatus(StrEnum):
    NEEDS_REVIEW = "needs_review"
    ACCEPTED = "accepted"
    RESOLVED = "resolved"


class RemediationActionType(StrEnum):
    RISK_ACCEPTED = "risk_accepted"
    REMEDIATION_REQUESTED = "remediation_requested"


class RiskAcceptanceReason(StrEnum):
    COMPATIBILITY_BLOCKED = "compatibility_blocked"
    LOW_CURRENT_IMPACT = "low_current_impact"
    OTHER = "other"


class WatchbackActionState(StrEnum):
    ACCEPTED = "accepted"
    REQUESTED = "requested"
    PR_OPEN = "pr_open"
    PR_MERGED = "pr_merged"
    VERIFICATION_PENDING = "verification_pending"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class GitHubAlertCounts(RemediationContractModel):
    open: int = Field(ge=0)
    fixed: int = Field(ge=0)
    dismissed: int = Field(ge=0)
    auto_dismissed: int = Field(ge=0)


class RemediationRepository(RemediationContractModel):
    id: UUID
    full_name: str
    display_name: str
    importance: Priority


class RemediationAlert(RemediationContractModel):
    id: UUID
    github_alert_number: int = Field(ge=1)
    state: AlertState
    cve_id: str
    ghsa_id: str
    vulnerable_version_range: str
    first_patched_version: str | None
    html_url: HttpUrl
    github_updated_at: datetime


class RemediationTarget(RemediationContractModel):
    id: str = Field(
        description="repository, ecosystem, dependency project root로 계산한 안정적인 읽기 모델 키"
    )
    repository: RemediationRepository
    project_root: str
    manifest_paths: list[str]
    manifest_path: str | None
    watchback_status: WatchbackGroupStatus
    github_alert_counts: GitHubAlertCounts
    case_ids: list[UUID]
    alerts: list[RemediationAlert]
    recommended_fix_versions: list[str] = Field(default_factory=list)
    representative_patched_version: str | None = None
    current_versions: list[str] = Field(default_factory=list)
    current_version_status: str = "unavailable"
    current_version_reason: str | None = None


class RemediationVulnerability(RemediationContractModel):
    cve_id: str
    ghsa_id: str
    advisory_summary: str
    advisory_severity: AdvisorySeverity
    priority: CandidatePriority
    candidate_id: UUID
    change_type: str
    reason_summary: str
    selected_at: datetime
    watchback_status: WatchbackGroupStatus = Field(
        description="연결 Case를 집계한 Watchback 처리 상태"
    )
    case_ids: list[UUID]
    alert_ids: list[UUID]
    evidence: list[EvidenceResponse] = Field(default_factory=list)
    deliveries: list[CandidateDelivery] = Field(default_factory=list)
    candidates: list[CandidateDetail] = Field(default_factory=list)


class RemediationAISummaryResponse(RemediationContractModel):
    prompt_version: str
    risk_summary: str
    action_summary: str
    interpretation_note: str | None = None
    model: str
    source_ids: list[str]
    generated_at: datetime


class RemediationHistoryEventType(StrEnum):
    RISK_ACCEPTED = "risk_accepted"
    RISK_ACCEPTANCE_REVOKED = "risk_acceptance_revoked"
    REMEDIATION_REQUESTED = "remediation_requested"


class RemediationHistoryItem(RemediationContractModel):
    id: str
    event_type: RemediationHistoryEventType
    watchback_state: WatchbackActionState
    reason_code: RiskAcceptanceReason | None
    note: str | None
    actor_user_id: UUID
    actor_display_name: str
    occurred_at: datetime
    target_count: int = Field(ge=0)
    pull_requests: list["RemediationPullRequest"] = Field(default_factory=list)


class RemediationGroup(RemediationContractModel):
    id: str = Field(description="organization, ecosystem, package로 계산한 읽기 모델 키")
    organization_id: UUID
    ecosystem: str
    package_name: str
    priority: CandidatePriority
    watchback_status: WatchbackGroupStatus
    github_alert_counts: GitHubAlertCounts
    cve_count: int = Field(ge=0)
    repository_count: int = Field(ge=0)
    recommended_fix_versions: list[str] = Field(
        description=(
            "연결 Alert가 제공한 고유 first_patched_version 목록. "
            "생태계별 버전 비교 없이 최고 버전을 임의 확정하지 않습니다."
        )
    )
    representative_patched_version: str | None = Field(
        description="동일 ecosystem 안에서 비교 가능한 수정 버전 중 가장 높은 조치 후보"
    )
    registered_at: datetime = Field(description="패키지 조치 후보에 연결된 최초 Case 등록 시각")
    updated_at: datetime
    ai_summary: RemediationAISummaryResponse | None = None
    action_history: list[RemediationHistoryItem] = Field(default_factory=list)
    targets: list[RemediationTarget]
    vulnerabilities: list[RemediationVulnerability]


class RemediationGroupListResponse(RemediationContractModel):
    items: list[RemediationGroup]
    total: int = Field(ge=0)


class RemediationActionCreate(RemediationContractModel):
    action_type: RemediationActionType
    target_ids: list[str] | None = Field(default=None, min_length=1)
    reason_code: RiskAcceptanceReason | None = None
    note: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def validate_reason(self) -> "RemediationActionCreate":
        if self.target_ids is not None:
            if len(set(self.target_ids)) != len(self.target_ids) or any(
                len(target_id) != 64
                or any(character not in "0123456789abcdef" for character in target_id)
                for target_id in self.target_ids
            ):
                raise ValueError("조치 대상 ID가 올바르지 않습니다.")
        note = self.note.strip() if self.note is not None else None
        if self.action_type is RemediationActionType.RISK_ACCEPTED:
            if self.reason_code is None:
                raise ValueError("위험 수용 사유를 선택해야 합니다.")
            if self.reason_code is RiskAcceptanceReason.OTHER and not note:
                raise ValueError("기타 위험 수용 사유를 입력해야 합니다.")
        else:
            if self.reason_code is not None:
                raise ValueError("조치 요청에는 위험 수용 사유를 사용할 수 없습니다.")
            if not note:
                raise ValueError("조치 요청 메모를 입력해야 합니다.")
        self.note = note
        return self


class RemediationActionTargetResponse(RemediationContractModel):
    review_case_id: UUID
    candidate_id: UUID
    alert_id: UUID
    repository_id: UUID
    repository_full_name: str
    manifest_path: str | None
    github_alert_number: int = Field(ge=1)
    github_alert_state_at_action: AlertState


class RemediationActionCreated(RemediationContractModel):
    id: UUID
    organization_id: UUID
    actor_user_id: UUID
    group_key: str
    ecosystem: str
    package_name: str
    action_type: RemediationActionType
    watchback_state: WatchbackActionState = Field(
        description="GitHub Alert 상태와 별도로 관리하는 Watchback 조치 상태"
    )
    reason_code: RiskAcceptanceReason | None
    note: str | None
    occurred_at: datetime
    targets: list[RemediationActionTargetResponse]


class RemediationPullRequestCreate(RemediationContractModel):
    target_ids: list[str] | None = Field(default=None, min_length=1)
    note: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def validate_targets(self) -> "RemediationPullRequestCreate":
        if self.target_ids is not None and (
            len(set(self.target_ids)) != len(self.target_ids)
            or any(
                len(target_id) != 64
                or any(character not in "0123456789abcdef" for character in target_id)
                for target_id in self.target_ids
            )
        ):
            raise ValueError("조치 대상 ID가 올바르지 않습니다.")
        self.note = self.note.strip() if self.note else None
        return self


class RemediationPullRequest(RemediationContractModel):
    repository_full_name: str
    project_root: str
    number: int = Field(ge=1)
    url: HttpUrl
    head_ref: str
    base_ref: str
    head_sha: str
    current_version: str
    target_version: str
    changed_files: list[str]
    merged: bool = False
    merge_sha: str | None = None
    merged_at: datetime | None = None
    closed: bool = False
    closed_at: datetime | None = None


class RemediationPullRequestBatchCreated(RemediationActionCreated):
    pull_requests: list[RemediationPullRequest]


class RemediationPullRequestMergeRequest(RemediationContractModel):
    action_id: UUID | None = None


class RemediationAlertVerification(RemediationContractModel):
    alert_id: UUID
    repository_full_name: str
    github_alert_number: int = Field(ge=1)
    state: AlertState
    fixed_at: datetime | None = None
    github_updated_at: datetime


class RemediationPullRequestMergeResponse(RemediationContractModel):
    action_id: UUID
    group_key: str
    watchback_state: WatchbackActionState
    pull_requests: list[RemediationPullRequest]
    alert_verifications: list[RemediationAlertVerification]


class RemediationPullRequestCloseResponse(RemediationContractModel):
    action_id: UUID
    group_key: str
    watchback_state: WatchbackActionState
    pull_requests: list[RemediationPullRequest]


class RemediationReopened(RemediationContractModel):
    group_key: str
    revoked_action_ids: list[UUID]
    reopened_at: datetime


class RemediationReopenRequest(RemediationContractModel):
    target_ids: list[str] | None = Field(default=None, min_length=1)
    note: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def validate_targets(self) -> "RemediationReopenRequest":
        if self.target_ids is not None and (
            len(set(self.target_ids)) != len(self.target_ids)
            or any(
                len(target_id) != 64
                or any(character not in "0123456789abcdef" for character in target_id)
                for target_id in self.target_ids
            )
        ):
            raise ValueError("재검토 대상 ID가 올바르지 않습니다.")
        self.note = self.note.strip() if self.note else None
        return self
