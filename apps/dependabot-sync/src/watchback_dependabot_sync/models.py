from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class SourceModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class RepositoryPayload(SourceModel):
    id: int = Field(gt=0)
    full_name: str = Field(min_length=3)
    default_branch: str | None = None
    updated_at: datetime


class PackagePayload(SourceModel):
    ecosystem: str = Field(min_length=1)
    name: str = Field(min_length=1)


class DependencyPayload(SourceModel):
    package: PackagePayload
    manifest_path: str | None = None
    scope: Literal["runtime", "development"] | None = None
    relationship: Literal["direct", "transitive", "unknown"] | None = None


class PatchedVersionPayload(SourceModel):
    identifier: str = Field(min_length=1)


class VulnerabilityPayload(SourceModel):
    package: PackagePayload
    severity: Literal["low", "medium", "high", "critical"]
    vulnerable_version_range: str = Field(min_length=1)
    first_patched_version: PatchedVersionPayload | None = None


class IdentifierPayload(SourceModel):
    value: str = Field(min_length=1)
    type: str = Field(min_length=1)


class CvssPayload(SourceModel):
    score: Decimal = Field(ge=0, le=10)
    vector_string: str | None = None


class CvssSeveritiesPayload(SourceModel):
    cvss_v3: CvssPayload | None = None
    cvss_v4: CvssPayload | None = None


class AdvisoryPayload(SourceModel):
    ghsa_id: str = Field(pattern=r"^GHSA-[A-Za-z0-9-]+$")
    cve_id: str | None = None
    summary: str = Field(min_length=1)
    description: str | None = None
    severity: Literal["low", "medium", "high", "critical"]
    identifiers: list[IdentifierPayload]
    published_at: datetime | None = None
    updated_at: datetime
    withdrawn_at: datetime | None = None
    cvss: CvssPayload | None = None
    cvss_severities: CvssSeveritiesPayload | None = None

    @property
    def effective_cvss_score(self) -> Decimal | None:
        versioned = self.cvss_severities
        for payload in (
            versioned.cvss_v4 if versioned else None,
            versioned.cvss_v3 if versioned else None,
            self.cvss,
        ):
            if payload and (payload.vector_string or payload.score > 0):
                return payload.score
        return None

    @model_validator(mode="after")
    def derive_and_verify_cve(self) -> Self:
        cves = sorted({item.value for item in self.identifiers if item.type.upper() == "CVE"})
        derived = cves[0] if cves else None
        if self.cve_id is not None and self.cve_id != derived:
            raise ValueError("cve_id와 identifiers의 CVE가 일치하지 않습니다.")
        self.cve_id = derived
        return self


class ActorPayload(SourceModel):
    login: str = Field(min_length=1)


class AlertPayload(SourceModel):
    number: int = Field(gt=0)
    state: Literal["open", "dismissed", "fixed", "auto_dismissed"]
    dependency: DependencyPayload
    security_advisory: AdvisoryPayload
    security_vulnerability: VulnerabilityPayload
    url: HttpUrl
    html_url: HttpUrl
    created_at: datetime
    updated_at: datetime
    dismissed_at: datetime | None = None
    dismissed_by: ActorPayload | None = None
    dismissed_reason: str | None = None
    dismissed_comment: str | None = None
    fixed_at: datetime | None = None
    auto_dismissed_at: datetime | None = None

    @model_validator(mode="after")
    def validate_source_consistency(self) -> Self:
        if self.dependency.package != self.security_vulnerability.package:
            raise ValueError("dependency와 security_vulnerability의 package가 다릅니다.")
        if self.security_advisory.severity != self.security_vulnerability.severity:
            raise ValueError("Advisory와 Vulnerability의 severity가 다릅니다.")
        if self.state == "open" and any(
            (self.dismissed_at, self.fixed_at, self.auto_dismissed_at)
        ):
            raise ValueError("open Alert에 종료 시각이 존재합니다.")
        if self.state == "dismissed" and self.dismissed_at is None:
            raise ValueError("dismissed Alert에는 dismissed_at이 필요합니다.")
        if self.state == "fixed" and self.fixed_at is None:
            raise ValueError("fixed Alert에는 fixed_at이 필요합니다.")
        if self.state == "auto_dismissed" and self.auto_dismissed_at is None:
            raise ValueError("auto_dismissed Alert에는 auto_dismissed_at이 필요합니다.")
        return self
