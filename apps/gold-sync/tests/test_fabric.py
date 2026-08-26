from __future__ import annotations

import pytest

from watchback_gold_sync.errors import SourceError
from watchback_gold_sync.fabric import FabricReader


class Cursor:
    def __init__(self) -> None:
        self.description = [("batch_id",)]
        self.queries: list[tuple[str, tuple[str, ...]]] = []
        self._rows: list[tuple[str]] = []

    def execute(self, query: str, params: tuple[str, ...]) -> None:
        self.queries.append((query, params))
        self._rows = [(item,) for item in params]

    def fetchall(self) -> list[tuple[str]]:
        return self._rows


def test_select_batches_uses_only_confirmed_batch_ids() -> None:
    cursor = Cursor()
    rows = FabricReader._select_batches(
        cursor,
        "publish_rereview_candidate",
        ("batch_id",),
        {"batch-2", "batch-1"},
    )

    assert rows == [{"batch_id": "batch-1"}, {"batch_id": "batch-2"}]
    assert cursor.queries[0][1] == ("batch-1", "batch-2")
    assert "WHERE [batch_id] IN (?, ?)" in cursor.queries[0][0]


def test_schema_check_allows_extra_columns_but_rejects_missing_contract_columns() -> None:
    observed = [
        {"column_name": "batch_id"},
        {"column_name": "status"},
        {"column_name": "extra_column"},
    ]
    FabricReader._verify_columns("batch", observed, ("batch_id", "status"))

    with pytest.raises(SourceError) as caught:
        FabricReader._verify_columns("batch", observed, ("batch_id", "as_of"))
    assert caught.value.code == "fabric_schema_mismatch"
    assert caught.value.context["missing_columns"] == ["as_of"]


def test_schema_check_rejects_incompatible_contract_column_type() -> None:
    observed = [
        {"column_name": "batch_id", "data_type": "varchar"},
        {"column_name": "as_of", "data_type": "datetime2"},
        {"column_name": "candidate_count", "data_type": "varchar"},
        {"column_name": "extra_column", "data_type": "xml"},
    ]

    with pytest.raises(SourceError) as caught:
        FabricReader._verify_types("publish_rereview_batch", observed)

    assert caught.value.code == "fabric_schema_mismatch"
    assert caught.value.context["incompatible_columns"] == [
        {"column": "candidate_count", "actual_type": "varchar"}
    ]
