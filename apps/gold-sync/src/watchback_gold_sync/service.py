from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from .config import Settings
from .errors import SyncError
from .fabric import FabricReader, RuntimeTokenCredential
from .models import BatchPayload, build_payloads
from .persistence import candidate_payload_hash, persist_batch


@dataclass(frozen=True)
class SyncResult:
    payload: dict[str, Any]
    has_failures: bool


def batch_digest(payload: BatchPayload) -> str:
    canonical = json.dumps(
        {
            "batch": payload.batch.model_dump(mode="json"),
            "candidates": [
                {
                    "candidate_id": item.candidate_id,
                    "payload_hash": candidate_payload_hash(
                        item,
                        [
                            evidence
                            for evidence in payload.evidence
                            if evidence.candidate_id == item.candidate_id
                        ],
                    ),
                }
                for item in sorted(payload.candidates, key=lambda item: item.candidate_id)
            ],
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def run_sync(
    settings: Settings,
    *,
    reader: FabricReader | None = None,
    now: datetime | None = None,
) -> SyncResult:
    credential = (
        RuntimeTokenCredential(settings.fabric_sql_access_token)
        if settings.fabric_sql_access_token
        else None
    )
    source = reader or FabricReader(
        settings.fabric_sql_server,
        settings.fabric_sql_database,
        credential=credential,
    )
    snapshot = source.read()
    payloads, failures = build_payloads(
        snapshot.batches,
        snapshot.candidates,
        snapshot.evidence,
    )
    synced_at = now or datetime.now(UTC)
    batches: list[dict[str, Any]] = []
    for payload in payloads:
        try:
            changes = persist_batch(settings.database_url, payload, synced_at)
            batches.append(
                {
                    "batch_id": payload.batch.batch_id,
                    "source_count": {
                        "candidates": len(payload.candidates),
                        "evidence": len(payload.evidence),
                    },
                    "sha256": batch_digest(payload),
                    "changes": changes,
                    "db_applied": True,
                }
            )
        except SyncError as exc:
            failures.append(
                {
                    "batch_id": payload.batch.batch_id,
                    "code": exc.code,
                    "message": str(exc),
                    **exc.context,
                    "db_applied": False,
                }
            )
    return SyncResult(
        payload={
            "source": {
                "database": settings.fabric_sql_database,
                "views": snapshot.schemas,
                "counts": {
                    "batches": len(snapshot.batches),
                    "candidates": len(snapshot.candidates),
                    "evidence": len(snapshot.evidence),
                },
            },
            "batches": batches,
            "failures": failures,
        },
        has_failures=bool(failures),
    )
