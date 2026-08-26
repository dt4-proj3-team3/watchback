from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Literal, Self
from urllib.parse import urlparse
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class CaseStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"


class CaseStatusFilter(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"
    ALL = "all"


class Priority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CandidatePriority(StrEnum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class CandidateSubjectType(StrEnum):
    CVE = "CVE"
    GHSA = "GHSA"


class AlertState(StrEnum):
    OPEN = "open"
    DISMISSED = "dismissed"
    FIXED = "fixed"
    AUTO_DISMISSED = "auto_dismissed"


class AdvisorySeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DependencyScope(StrEnum):
    RUNTIME = "runtime"
    DEVELOPMENT = "development"


class DependencyRelationship(StrEnum):
    DIRECT = "direct"
    TRANSITIVE = "transitive"
    UNKNOWN = "unknown"


class CaseSort(StrEnum):
    PRIORITY = "priority"
    OPENED_AT = "opened_at"
    UPDATED_AT = "updated_at"


class SortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"


class UserActivityType(StrEnum):
    REVIEW_DEFERRED = "review_deferred"
    RISK_ACCEPTED = "risk_accepted"
    REMEDIATION_REQUESTED = "remediation_requested"
    NOTE_ADDED = "note_added"
    EXTERNAL_LINK_ADDED = "external_link_added"


class ActivityType(StrEnum):
    CASE_OPENED = "case_opened"
    CASE_REOPENED = "case_reopened"
    CASE_RESOLVED = "case_resolved"
    REVIEW_DEFERRED = "review_deferred"
    RISK_ACCEPTED = "risk_accepted"
    REMEDIATION_REQUESTED = "remediation_requested"
    NOTE_ADDED = "note_added"
    EXTERNAL_LINK_ADDED = "external_link_added"


class LinkType(StrEnum):
    ISSUE = "issue"
    PULL_REQUEST = "pull_request"


class EvidenceValueType(StrEnum):
    BOOLEAN = "boolean"
    DECIMAL = "decimal"
    VERSION = "version"
    TIMESTAMP = "timestamp"
    TEXT = "text"


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class ErrorResponse(ContractModel):
    code: str
    message: str
    details: dict[str, Any] | list[Any] | None = None


class RepositorySummary(ContractModel):
    id: UUID
    full_name: str
    display_name: str
    importance: Priority


class AlertSummary(ContractModel):
    id: UUID
    github_alert_number: int = Field(ge=1)
    state: AlertState
    package_name: str
    ecosystem: str
    first_patched_version: str | None
    html_url: HttpUrl


class AlertDetail(AlertSummary):
    manifest_path: str | None
    dependency_scope: DependencyScope | None
    dependency_relationship: DependencyRelationship | None
    vulnerable_version_range: str
    github_created_at: datetime
    github_updated_at: datetime
    dismissed_at: datetime | None
    dismissed_reason: str | None
    dismissed_by: str | None
    dismissed_comment: str | None
    fixed_at: datetime | None
    auto_dismissed_at: datetime | None


class AdvisorySummary(ContractModel):
    ghsa_id: str
    cve_id: str | None
    summary: str
    severity: AdvisorySeverity
    cvss_score: float | None = Field(ge=0, le=10)


class CandidateSummary(ContractModel):
    id: UUID
    source_candidate_id: str
    subject_type: CandidateSubjectType
    subject_id: str
    ghsa_id: str
    cve_id: str | None
    priority: CandidatePriority
    change_type: str
    reason_summary: str
    selected_at: datetime


class CandidateDelivery(ContractModel):
    batch_id: UUID
    source_batch_id: str
    as_of: datetime
    source_generated_at: datetime
    policy_version: str
    schema_version: str
    received_at: datetime


class EvidenceResponse(ContractModel):
    id: UUID
    source_evidence_id: str
    batch_id: UUID
    signal: str
    value_type: EvidenceValueType
    previous_value: str | None
    current_value: str | None
    observed_at: datetime
    source: str
    evidence_summary: str


class CandidateDetail(CandidateSummary):
    deliveries: list[CandidateDelivery] = Field(
        description="Gold Batch 전달 시각의 오름차순 이력"
    )
    evidence: list[EvidenceResponse] = Field(
        description="위험 신호 관찰 시각의 오름차순 근거"
    )


class ActorSummary(ContractModel):
    id: UUID
    display_name: str


class ExternalLinkCreate(ContractModel):
    link_type: LinkType
    url: HttpUrl

    @model_validator(mode="after")
    def validate_github_resource_url(self) -> Self:
        parsed = urlparse(str(self.url))
        path_parts = [part for part in parsed.path.split("/") if part]
        expected_segment = "issues" if self.link_type is LinkType.ISSUE else "pull"
        if parsed.hostname != "github.com" or len(path_parts) != 4:
            raise ValueError("GitHub Issue 또는 Pull Request URL이어야 합니다.")
        if path_parts[2] != expected_segment or not path_parts[3].isdigit():
            raise ValueError("link_type과 GitHub URL의 대상 유형이 일치해야 합니다.")
        return self


class ExternalLinkResponse(ContractModel):
    id: UUID
    link_type: LinkType
    url: HttpUrl
    github_owner: str
    github_repository: str
    github_number: int
    external_state: str | None
    github_updated_at: datetime | None
    last_synced_at: datetime | None


class ReviewActivityResponse(ContractModel):
    id: UUID
    candidate_id: UUID | None
    activity_type: ActivityType
    note: str | None
    actor: ActorSummary | None
    occurred_at: datetime
    created_at: datetime
    external_links: list[ExternalLinkResponse]


class CreatedReviewActivityResponse(ReviewActivityResponse):
    activity_type: UserActivityType
    actor: ActorSummary


class ReviewCaseSummary(ContractModel):
    id: UUID
    status: CaseStatus
    priority: Priority
    review_reason: str
    opened_at: datetime
    resolved_at: datetime | None
    last_reopened_at: datetime | None
    reopened_count: int = Field(ge=0)
    updated_at: datetime
    repository: RepositorySummary
    alert: AlertSummary
    advisory: AdvisorySummary
    latest_candidate: CandidateSummary = Field(
        description="연결된 Candidate 중 selected_at이 가장 최신인 항목"
    )


class ReviewCaseListResponse(ContractModel):
    items: list[ReviewCaseSummary]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total: int = Field(ge=0, description="현재 필터에 맞는 전체 Case 수")


class ReviewCaseDetail(ReviewCaseSummary):
    alert: AlertDetail
    candidates: list[CandidateDetail] = Field(
        description="선정 시각의 오름차순으로 정렬된 전체 위험 후보 이력"
    )
    activities: list[ReviewActivityResponse] = Field(
        description="활동 발생 시각의 오름차순 이력"
    )


class ActivityCreateBase(ContractModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    external_link: ExternalLinkCreate | None = None


class DecisionActivityCreate(ActivityCreateBase):
    activity_type: Literal[
        UserActivityType.REVIEW_DEFERRED,
        UserActivityType.RISK_ACCEPTED,
        UserActivityType.REMEDIATION_REQUESTED,
    ]
    candidate_id: UUID
    note: str = Field(min_length=1, max_length=2000)


class NoteActivityCreate(ActivityCreateBase):
    activity_type: Literal[UserActivityType.NOTE_ADDED]
    candidate_id: UUID | None = None
    note: str = Field(min_length=1, max_length=2000)


class ExternalLinkActivityCreate(ContractModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    activity_type: Literal[UserActivityType.EXTERNAL_LINK_ADDED]
    candidate_id: UUID | None = None
    note: str | None = Field(default=None, min_length=1, max_length=2000)
    external_link: ExternalLinkCreate


ReviewActivityCreate = Annotated[
    DecisionActivityCreate | NoteActivityCreate | ExternalLinkActivityCreate,
    Field(discriminator="activity_type"),
]


class ReviewActivityCreated(ContractModel):
    case_status: CaseStatus
    activity: CreatedReviewActivityResponse


EMPTY_LIST_EXAMPLE = {
    "items": [],
    "page": 1,
    "page_size": 20,
    "total": 0,
}

LIST_EXAMPLE = {
    "items": [
        {
            "id": "30000000-0000-0000-0000-000000000001",
            "status": "open",
            "priority": "critical",
            "review_reason": "KEV 등재와 패치 버전 등장을 다시 검토해야 합니다.",
            "opened_at": "2026-08-20T01:00:00Z",
            "resolved_at": None,
            "last_reopened_at": None,
            "reopened_count": 0,
            "updated_at": "2026-08-20T01:00:00Z",
            "repository": {
                "id": "10000000-0000-0000-0000-000000000001",
                "full_name": "dt4-proj3-team3/watchback-vulnerable-fe-lab",
                "display_name": "novalink/customer-fe",
                "importance": "critical",
            },
            "alert": {
                "id": "20000000-0000-0000-0000-000000000001",
                "github_alert_number": 12,
                "state": "open",
                "package_name": "example-package",
                "ecosystem": "npm",
                "first_patched_version": "2.0.1",
                "html_url": "https://github.com/dt4-proj3-team3/watchback-vulnerable-fe-lab/security/dependabot/12",
            },
            "advisory": {
                "ghsa_id": "GHSA-xxxx-yyyy-zzzz",
                "cve_id": "CVE-2026-12345",
                "summary": "예시 보안 권고",
                "severity": "critical",
                "cvss_score": 9.8,
            },
            "latest_candidate": {
                "id": "40000000-0000-0000-0000-000000000001",
                "source_candidate_id": "candidate-2026-08-20-001",
                "subject_type": "CVE",
                "subject_id": "CVE-2026-12345",
                "ghsa_id": "GHSA-xxxx-yyyy-zzzz",
                "cve_id": "CVE-2026-12345",
                "priority": "P0",
                "change_type": "kev_added",
                "reason_summary": "KEV에 새로 등재되었습니다.",
                "selected_at": "2026-08-20T00:30:00Z",
            },
        }
    ],
    "page": 1,
    "page_size": 20,
    "total": 1,
}

DETAIL_EXAMPLE = {
    **LIST_EXAMPLE["items"][0],
    "alert": {
        **LIST_EXAMPLE["items"][0]["alert"],
        "manifest_path": "package-lock.json",
        "dependency_scope": "runtime",
        "dependency_relationship": "direct",
        "vulnerable_version_range": "< 2.0.1",
        "github_created_at": "2026-08-01T00:00:00Z",
        "github_updated_at": "2026-08-20T00:10:00Z",
        "dismissed_at": None,
        "dismissed_reason": None,
        "dismissed_by": None,
        "dismissed_comment": None,
        "fixed_at": None,
        "auto_dismissed_at": None,
    },
    "candidates": [
        {
            **LIST_EXAMPLE["items"][0]["latest_candidate"],
            "deliveries": [
                {
                    "batch_id": "50000000-0000-0000-0000-000000000001",
                    "source_batch_id": "gold-2026-08-20T00:40:00Z",
                    "as_of": "2026-08-20T00:30:00Z",
                    "source_generated_at": "2026-08-20T00:40:00Z",
                    "policy_version": "sp1-v1",
                    "schema_version": "1.0",
                    "received_at": "2026-08-20T00:45:00Z",
                }
            ],
            "evidence": [
                {
                    "id": "60000000-0000-0000-0000-000000000001",
                    "source_evidence_id": "evidence-2026-08-20-001",
                    "batch_id": "50000000-0000-0000-0000-000000000001",
                    "signal": "kev",
                    "value_type": "boolean",
                    "previous_value": "false",
                    "current_value": "true",
                    "observed_at": "2026-08-20T00:20:00Z",
                    "source": "cisa_kev",
                    "evidence_summary": "CISA KEV에 새로 등재되었습니다.",
                }
            ],
        }
    ],
    "activities": [],
}

ACTIVITY_REQUEST_EXAMPLE = {
    "activity_type": "risk_accepted",
    "candidate_id": "40000000-0000-0000-0000-000000000001",
    "note": "현재 위험을 검토한 뒤 수용합니다.",
    "external_link": {
        "link_type": "issue",
        "url": "https://github.com/dt4-proj3-team3/watchback-vulnerable-fe-lab/issues/21",
    },
}

ACTIVITY_RESPONSE_EXAMPLE = {
    "case_status": "resolved",
    "activity": {
        "id": "70000000-0000-0000-0000-000000000001",
        "candidate_id": "40000000-0000-0000-0000-000000000001",
        "activity_type": "risk_accepted",
        "note": "현재 위험을 검토한 뒤 수용합니다.",
        "actor": {
            "id": "80000000-0000-0000-0000-000000000001",
            "display_name": "Watchback Reviewer",
        },
        "occurred_at": "2026-08-20T02:00:00Z",
        "created_at": "2026-08-20T02:00:00Z",
        "external_links": [
            {
                "id": "90000000-0000-0000-0000-000000000001",
                "link_type": "issue",
                "url": "https://github.com/dt4-proj3-team3/watchback-vulnerable-fe-lab/issues/21",
                "github_owner": "dt4-proj3-team3",
                "github_repository": "watchback-vulnerable-fe-lab",
                "github_number": 21,
                "external_state": None,
                "github_updated_at": None,
                "last_synced_at": None,
            }
        ],
    },
}
