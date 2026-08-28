from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .errors import ContractError


class CandidatePriority(StrEnum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class SubjectType(StrEnum):
    CVE = "CVE"


class EvidenceValueType(StrEnum):
    BOOLEAN = "boolean"
    DECIMAL = "decimal"
    VERSION = "version"
    TIMESTAMP = "timestamp"
    TEXT = "text"


class SourceModel(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    @field_validator("*", mode="before")
    @classmethod
    def normalize_timestamp(cls, value: Any, info: Any) -> Any:
        if info.field_name.endswith("_at") or info.field_name == "as_of":
            if isinstance(value, datetime) and value.tzinfo is None:
                return value.replace(tzinfo=UTC)
        return value


class BatchRow(SourceModel):
    batch_id: str = Field(min_length=1)
    ds_run_id: str | None = None
    status: Literal["completed"]
    as_of: datetime
    generated_at: datetime
    policy_version: str = Field(min_length=1)
    schema_version: str = Field(min_length=1)
    candidate_count: int = Field(ge=0)


class CandidateRow(SourceModel):
    batch_id: str = Field(min_length=1)
    candidate_id: str = Field(min_length=1)
    subject_type: SubjectType
    subject_id: str = Field(min_length=1)
    ghsa_id: str | None = Field(default=None, min_length=1)
    cve_id: str = Field(min_length=1)
    priority: CandidatePriority
    change_type: str = Field(min_length=1)
    reason_summary: str = Field(min_length=1)
    selected_at: datetime

    @model_validator(mode="after")
    def validate_subject(self) -> Self:
        if self.subject_id != self.cve_id:
            raise ValueError("CVE subject는 cve_id와 subject_id가 같아야 합니다.")
        return self


class EvidenceRow(SourceModel):
    batch_id: str = Field(min_length=1)
    evidence_id: str = Field(min_length=1)
    candidate_id: str = Field(min_length=1)
    signal: str = Field(min_length=1)
    value_type: EvidenceValueType
    previous_value: str | None = None
    current_value: str | None = None
    observed_at: datetime
    source: str = Field(min_length=1)
    evidence_summary: str = Field(min_length=1)


class BatchPayload(BaseModel):
    batch: BatchRow
    candidates: list[CandidateRow]
    evidence: list[EvidenceRow]

    @model_validator(mode="after")
    def validate_grain_and_relationships(self) -> Self:
        candidate_ids = [item.candidate_id for item in self.candidates]
        evidence_ids = [item.evidence_id for item in self.evidence]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("Batch 안에 중복 candidate_id가 있습니다.")
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("Batch 안에 중복 evidence_id가 있습니다.")
        if self.batch.candidate_count != len(candidate_ids):
            raise ValueError("candidate_count와 Candidate 행 수가 다릅니다.")
        known = set(candidate_ids)
        missing = sorted({item.candidate_id for item in self.evidence} - known)
        if missing:
            raise ValueError(f"Candidate 없는 Evidence가 있습니다: {missing}")
        if any(item.batch_id != self.batch.batch_id for item in self.candidates):
            raise ValueError("Candidate의 batch_id가 Batch와 다릅니다.")
        if any(item.batch_id != self.batch.batch_id for item in self.evidence):
            raise ValueError("Evidence의 batch_id가 Batch와 다릅니다.")
        return self


def build_payloads(
    batch_rows: list[dict[str, Any]],
    candidate_rows: list[dict[str, Any]],
    evidence_rows: list[dict[str, Any]],
) -> tuple[list[BatchPayload], list[dict[str, Any]]]:
    failures: list[dict[str, Any]] = []
    raw_batch_ids = [str(item.get("batch_id", "")) for item in batch_rows]
    duplicated = sorted(
        {item for item in raw_batch_ids if item and raw_batch_ids.count(item) > 1}
    )
    if duplicated:
        raise ContractError(
            "duplicate_batch_grain",
            "Batch View에 중복 batch_id가 있습니다.",
            context={"batch_ids": duplicated},
        )

    known_batches = set(raw_batch_ids)
    orphan_batches = sorted(
        {
            str(item.get("batch_id", ""))
            for item in [*candidate_rows, *evidence_rows]
            if str(item.get("batch_id", "")) not in known_batches
        }
    )
    if orphan_batches:
        failures.append(
            {
                "batch_id": None,
                "code": "orphan_batch_reference",
                "message": "Batch View에 없는 batch_id를 참조합니다.",
                "references": orphan_batches,
                "db_applied": False,
            }
        )

    payloads: list[BatchPayload] = []
    for raw_batch in batch_rows:
        batch_id = str(raw_batch.get("batch_id", ""))
        try:
            payloads.append(
                BatchPayload.model_validate(
                    {
                        "batch": raw_batch,
                        "candidates": [
                            item for item in candidate_rows if item.get("batch_id") == batch_id
                        ],
                        "evidence": [
                            item for item in evidence_rows if item.get("batch_id") == batch_id
                        ],
                    }
                )
            )
        except ValueError as exc:
            failures.append(
                {
                    "batch_id": batch_id or None,
                    "code": "contract_violation",
                    "message": str(exc),
                    "db_applied": False,
                }
            )
    payloads.sort(key=lambda item: (item.batch.generated_at, item.batch.batch_id))
    return payloads, failures
