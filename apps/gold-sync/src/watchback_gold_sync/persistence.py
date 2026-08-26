from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

import psycopg
from psycopg.rows import dict_row

from .errors import PersistenceError
from .models import BatchPayload, CandidateRow, EvidenceRow


LOCK_KEY = 126090


def normalize_database_url(url: str) -> str:
    return url.replace("postgresql+psycopg://", "postgresql://", 1).replace(
        "postgresql+psycopg2://", "postgresql://", 1
    )


def batch_uuid(source_batch_id: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"watchback:gold-batch:{source_batch_id}")


def candidate_uuid(source_candidate_id: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"watchback:risk-candidate:{source_candidate_id}")


def evidence_uuid(source_batch_id: str, source_evidence_id: str) -> UUID:
    return uuid5(
        NAMESPACE_URL,
        f"watchback:candidate-evidence:{source_batch_id}:{source_evidence_id}",
    )


def candidate_payload_hash(
    candidate: CandidateRow, evidence: list[EvidenceRow]
) -> str:
    canonical = json.dumps(
        {
            "candidate": candidate.model_dump(mode="json"),
            "evidence": [
                item.model_dump(mode="json")
                for item in sorted(evidence, key=lambda item: item.evidence_id)
            ],
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


@dataclass
class ChangeCounts:
    created: int = 0
    updated: int = 0
    unchanged: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "created": self.created,
            "updated": self.updated,
            "unchanged": self.unchanged,
        }


@dataclass
class BatchChanges:
    batch: ChangeCounts = field(default_factory=ChangeCounts)
    candidates: ChangeCounts = field(default_factory=ChangeCounts)
    deliveries: ChangeCounts = field(default_factory=ChangeCounts)
    evidence: ChangeCounts = field(default_factory=ChangeCounts)

    def as_dict(self) -> dict[str, dict[str, int]]:
        return {
            "batch": self.batch.as_dict(),
            "candidates": self.candidates.as_dict(),
            "deliveries": self.deliveries.as_dict(),
            "evidence": self.evidence.as_dict(),
        }


def _candidate_values(candidate: CandidateRow) -> tuple[Any, ...]:
    return (
        candidate.subject_type.value,
        candidate.subject_id,
        candidate.ghsa_id,
        candidate.cve_id,
        candidate.priority.value,
        candidate.change_type,
        candidate.reason_summary,
        candidate.selected_at,
    )


def _assert_existing_batch(
    cursor: psycopg.Cursor[Any], payload: BatchPayload, batch_id: UUID
) -> BatchChanges:
    batch = payload.batch
    cursor.execute(
        """
        SELECT ds_run_id, as_of, source_generated_at, policy_version,
               schema_version, candidate_count
          FROM gold_batches
         WHERE id = %s
        """,
        (batch_id,),
    )
    existing = cursor.fetchone()
    expected_batch = {
        "ds_run_id": batch.ds_run_id,
        "as_of": batch.as_of,
        "source_generated_at": batch.generated_at,
        "policy_version": batch.policy_version,
        "schema_version": batch.schema_version,
        "candidate_count": batch.candidate_count,
    }
    if existing is None or any(existing[key] != value for key, value in expected_batch.items()):
        raise PersistenceError(
            "completed_batch_changed",
            "이미 적재된 완료 Batch의 원본 필드가 달라졌습니다.",
            context={"batch_id": batch.batch_id},
        )

    cursor.execute(
        """
        SELECT rc.source_candidate_id, gbc.payload_hash
          FROM gold_batch_candidates gbc
          JOIN risk_candidates rc ON rc.id = gbc.candidate_id
         WHERE gbc.batch_id = %s
        """,
        (batch_id,),
    )
    observed = {row["source_candidate_id"]: row["payload_hash"] for row in cursor.fetchall()}
    expected = {
        candidate.candidate_id: candidate_payload_hash(
            candidate,
            [item for item in payload.evidence if item.candidate_id == candidate.candidate_id],
        )
        for candidate in payload.candidates
    }
    if observed != expected:
        raise PersistenceError(
            "completed_batch_changed",
            "이미 적재된 완료 Batch의 Candidate payload가 달라졌습니다.",
            context={"batch_id": batch.batch_id},
        )
    changes = BatchChanges()
    changes.batch.unchanged = 1
    changes.candidates.unchanged = len(payload.candidates)
    changes.deliveries.unchanged = len(payload.candidates)
    changes.evidence.unchanged = len(payload.evidence)
    return changes


def _upsert_candidate(
    cursor: psycopg.Cursor[Any],
    candidate: CandidateRow,
    generated_at: datetime,
) -> tuple[UUID, str]:
    cursor.execute(
        """
        SELECT id, subject_type, subject_id, ghsa_id, cve_id, priority,
               change_type, reason_summary, selected_at
          FROM risk_candidates
         WHERE source_candidate_id = %s
        """,
        (candidate.candidate_id,),
    )
    existing = cursor.fetchone()
    values = _candidate_values(candidate)
    if existing is None:
        identifier = candidate_uuid(candidate.candidate_id)
        cursor.execute(
            """
            INSERT INTO risk_candidates
                (id, source_candidate_id, subject_type, subject_id, ghsa_id, cve_id,
                 priority, change_type, reason_summary, selected_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (identifier, candidate.candidate_id, *values),
        )
        return identifier, "created"

    current_values = tuple(
        existing[key]
        for key in (
            "subject_type",
            "subject_id",
            "ghsa_id",
            "cve_id",
            "priority",
            "change_type",
            "reason_summary",
            "selected_at",
        )
    )
    cursor.execute(
        """
        SELECT max(gb.source_generated_at) AS latest_generated_at
          FROM gold_batch_candidates gbc
          JOIN gold_batches gb ON gb.id = gbc.batch_id
         WHERE gbc.candidate_id = %s
        """,
        (existing["id"],),
    )
    latest_generated_at = cursor.fetchone()["latest_generated_at"]
    if current_values == values or latest_generated_at is None or generated_at < latest_generated_at:
        return existing["id"], "unchanged"
    if generated_at == latest_generated_at:
        raise PersistenceError(
            "candidate_generation_conflict",
            "동일 생성 시각의 Candidate payload가 서로 다릅니다.",
            context={"candidate_id": candidate.candidate_id},
        )
    cursor.execute(
        """
        UPDATE risk_candidates
           SET subject_type = %s, subject_id = %s, ghsa_id = %s, cve_id = %s,
               priority = %s, change_type = %s, reason_summary = %s,
               selected_at = %s, updated_at = now()
         WHERE id = %s
        """,
        (*values, existing["id"]),
    )
    return existing["id"], "updated"


def persist_batch(
    database_url: str,
    payload: BatchPayload,
    synced_at: datetime,
) -> dict[str, dict[str, int]]:
    batch = payload.batch
    identifier = batch_uuid(batch.batch_id)
    changes = BatchChanges()
    try:
        with psycopg.connect(
            normalize_database_url(database_url), row_factory=dict_row
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(%s)", (LOCK_KEY,))
                cursor.execute(
                    "SELECT id FROM gold_batches WHERE source_batch_id = %s",
                    (batch.batch_id,),
                )
                existing_batch = cursor.fetchone()
                if existing_batch is not None:
                    return _assert_existing_batch(cursor, payload, existing_batch["id"]).as_dict()

                cursor.execute(
                    """
                    INSERT INTO gold_batches
                        (id, source_batch_id, ds_run_id, as_of, source_generated_at,
                         policy_version, schema_version, candidate_count, synced_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        identifier,
                        batch.batch_id,
                        batch.ds_run_id,
                        batch.as_of,
                        batch.generated_at,
                        batch.policy_version,
                        batch.schema_version,
                        batch.candidate_count,
                        synced_at,
                    ),
                )
                changes.batch.created = 1

                for candidate in payload.candidates:
                    candidate_id, action = _upsert_candidate(
                        cursor, candidate, batch.generated_at
                    )
                    setattr(changes.candidates, action, getattr(changes.candidates, action) + 1)
                    evidence = [
                        item
                        for item in payload.evidence
                        if item.candidate_id == candidate.candidate_id
                    ]
                    cursor.execute(
                        """
                        INSERT INTO gold_batch_candidates
                            (batch_id, candidate_id, payload_hash, received_at)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (
                            identifier,
                            candidate_id,
                            candidate_payload_hash(candidate, evidence),
                            synced_at,
                        ),
                    )
                    changes.deliveries.created += 1
                    for item in evidence:
                        cursor.execute(
                            """
                            INSERT INTO candidate_evidence
                                (id, source_evidence_id, batch_id, candidate_id, signal,
                                 value_type, previous_value, current_value, observed_at,
                                 source, evidence_summary)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """,
                            (
                                evidence_uuid(batch.batch_id, item.evidence_id),
                                item.evidence_id,
                                identifier,
                                candidate_id,
                                item.signal,
                                item.value_type.value,
                                item.previous_value,
                                item.current_value,
                                item.observed_at,
                                item.source,
                                item.evidence_summary,
                            ),
                        )
                        changes.evidence.created += 1
        return changes.as_dict()
    except PersistenceError:
        raise
    except psycopg.Error as exc:
        raise PersistenceError(
            "database_write_failed",
            "Gold Batch를 PostgreSQL에 반영하지 못했습니다.",
            context={"batch_id": batch.batch_id},
        ) from exc
