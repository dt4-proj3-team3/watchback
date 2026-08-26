from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta

import psycopg
import pytest

from test_models import rows
from watchback_gold_sync.config import Settings
from watchback_gold_sync.errors import PersistenceError
from watchback_gold_sync.fabric import FabricSnapshot
from watchback_gold_sync.models import build_payloads
from watchback_gold_sync.persistence import normalize_database_url, persist_batch
from watchback_gold_sync.service import run_sync


NOW = datetime(2026, 8, 26, tzinfo=UTC)


@pytest.fixture(autouse=True)
def clean_gold_tables(database_url: str):
    yield
    with psycopg.connect(normalize_database_url(database_url)) as connection:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM candidate_evidence")
            cursor.execute("DELETE FROM gold_batch_candidates")
            cursor.execute("DELETE FROM risk_candidates")
            cursor.execute("DELETE FROM gold_batches")


def count_rows(database_url: str) -> dict[str, int]:
    with psycopg.connect(normalize_database_url(database_url)) as connection:
        with connection.cursor() as cursor:
            result = {}
            for table in (
                "gold_batches",
                "risk_candidates",
                "gold_batch_candidates",
                "candidate_evidence",
            ):
                cursor.execute(f"SELECT count(*) FROM {table}")
                result[table] = cursor.fetchone()[0]
            return result


def test_persists_and_replays_same_batch_without_changes(database_url: str) -> None:
    payload = build_payloads(*rows())[0][0]
    first = persist_batch(database_url, payload, NOW)
    second = persist_batch(database_url, payload, NOW + timedelta(minutes=1))

    assert first["batch"]["created"] == 1
    assert first["candidates"]["created"] == 2
    assert first["evidence"]["created"] == 2
    assert second["batch"]["unchanged"] == 1
    assert second["deliveries"]["unchanged"] == 2
    assert count_rows(database_url) == {
        "gold_batches": 1,
        "risk_candidates": 2,
        "gold_batch_candidates": 2,
        "candidate_evidence": 2,
    }


def test_same_evidence_id_is_scoped_to_batch(database_url: str) -> None:
    first = build_payloads(*rows())[0][0]
    persist_batch(database_url, first, NOW)

    batches, candidates, evidence = rows()
    batches[0].update(
        batch_id="batch-2",
        generated_at="2026-08-22T01:00:00Z",
        candidate_count=1,
    )
    candidates = [candidates[0] | {"batch_id": "batch-2"}]
    evidence = [evidence[0] | {"batch_id": "batch-2"}]
    second = build_payloads(batches, candidates, evidence)[0][0]
    result = persist_batch(database_url, second, NOW + timedelta(days=1))

    assert result["candidates"]["unchanged"] == 1
    assert count_rows(database_url)["candidate_evidence"] == 3


def test_rejects_changed_completed_batch_atomically(database_url: str) -> None:
    original = build_payloads(*rows())[0][0]
    persist_batch(database_url, original, NOW)
    batches, candidates, evidence = deepcopy(rows())
    evidence[0]["current_value"] = "false"
    changed = build_payloads(batches, candidates, evidence)[0][0]

    with pytest.raises(PersistenceError, match="완료 Batch"):
        persist_batch(database_url, changed, NOW + timedelta(minutes=1))
    assert count_rows(database_url)["candidate_evidence"] == 2


class FakeReader:
    def __init__(self, snapshot: FabricSnapshot) -> None:
        self.snapshot = snapshot

    def read(self) -> FabricSnapshot:
        return self.snapshot


def test_invalid_batch_does_not_rollback_valid_batch(database_url: str) -> None:
    batches, candidates, evidence = rows()
    invalid_batch = deepcopy(batches[0])
    invalid_batch.update(batch_id="batch-invalid", candidate_count=1)
    batches.append(invalid_batch)
    settings = Settings("example", "watchback_lakehouse_dev_v2", database_url)
    snapshot = FabricSnapshot({}, batches, candidates, evidence)

    result = run_sync(settings, reader=FakeReader(snapshot), now=NOW)

    assert result.has_failures is True
    assert result.payload["batches"][0]["batch_id"] == "batch-1"
    assert result.payload["failures"][0]["batch_id"] == "batch-invalid"
    assert count_rows(database_url)["gold_batches"] == 1
