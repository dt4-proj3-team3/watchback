from __future__ import annotations

import struct
import time
from dataclasses import dataclass
from typing import Any, Callable

from azure.core.credentials import AccessToken, TokenCredential
from azure.identity import DefaultAzureCredential

from .config import BATCH_VIEW, CANDIDATE_VIEW, EVIDENCE_VIEW, FABRIC_SCHEMA
from .errors import SourceError


SQL_COPT_SS_ACCESS_TOKEN = 1256
TOKEN_SCOPE = "https://database.windows.net/.default"

BATCH_COLUMNS = (
    "batch_id",
    "ds_run_id",
    "status",
    "as_of",
    "generated_at",
    "policy_version",
    "schema_version",
    "candidate_count",
)
CANDIDATE_COLUMNS = (
    "batch_id",
    "candidate_id",
    "subject_type",
    "subject_id",
    "ghsa_id",
    "cve_id",
    "priority",
    "change_type",
    "reason_summary",
    "selected_at",
)
EVIDENCE_COLUMNS = (
    "batch_id",
    "evidence_id",
    "candidate_id",
    "signal",
    "value_type",
    "previous_value",
    "current_value",
    "observed_at",
    "source",
    "evidence_summary",
)

STRING_TYPES = {"char", "nchar", "nvarchar", "varchar"}
TIMESTAMP_TYPES = {"datetime", "datetime2", "datetimeoffset", "smalldatetime"}
INTEGER_TYPES = {"bigint", "int", "smallint", "tinyint"}

EXPECTED_COLUMN_TYPES = {
    BATCH_VIEW: {
        **{column: STRING_TYPES for column in BATCH_COLUMNS},
        "as_of": TIMESTAMP_TYPES,
        "generated_at": TIMESTAMP_TYPES,
        "candidate_count": INTEGER_TYPES,
    },
    CANDIDATE_VIEW: {
        **{column: STRING_TYPES for column in CANDIDATE_COLUMNS},
        "selected_at": TIMESTAMP_TYPES,
    },
    EVIDENCE_VIEW: {
        **{column: STRING_TYPES for column in EVIDENCE_COLUMNS},
        "observed_at": TIMESTAMP_TYPES,
    },
}


@dataclass(frozen=True)
class FabricSnapshot:
    schemas: dict[str, list[dict[str, Any]]]
    batches: list[dict[str, Any]]
    candidates: list[dict[str, Any]]
    evidence: list[dict[str, Any]]


class RuntimeTokenCredential:
    """프로세스 환경으로 전달된 단기 Fabric 토큰을 사용한다."""

    def __init__(self, token: str) -> None:
        self._token = token

    def get_token(self, *_scopes: str, **_kwargs: Any) -> AccessToken:
        return AccessToken(self._token, int(time.time()) + 300)


class FabricReader:
    def __init__(
        self,
        server: str,
        database: str,
        *,
        credential: TokenCredential | None = None,
        connector: Callable[..., Any] | None = None,
    ) -> None:
        self.server = server
        self.database = database
        self.credential = credential or DefaultAzureCredential()
        if connector is None:
            try:
                import pyodbc
            except ImportError as exc:
                raise SourceError(
                    "odbc_driver_unavailable",
                    "pyodbc 또는 시스템 ODBC Driver를 불러오지 못했습니다.",
                ) from exc
            connector = pyodbc.connect
        self.connector = connector

    def _connect(self) -> Any:
        try:
            token = self.credential.get_token(TOKEN_SCOPE).token.encode("utf-16-le")
            token_struct = struct.pack(f"<I{len(token)}s", len(token), token)
            connection_string = (
                "DRIVER={ODBC Driver 18 for SQL Server};"
                f"SERVER=tcp:{self.server},1433;"
                f"DATABASE={self.database};"
                "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
            )
            return self.connector(
                connection_string,
                attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct},
            )
        except SourceError:
            raise
        except Exception as exc:
            raise SourceError(
                "fabric_connection_failed",
                "Fabric SQL Analytics Endpoint 연결에 실패했습니다.",
            ) from exc

    @staticmethod
    def _rows(cursor: Any) -> list[dict[str, Any]]:
        columns = [item[0] for item in cursor.description]
        return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]

    def _schema(self, cursor: Any, view: str) -> list[dict[str, Any]]:
        cursor.execute(
            """
            SELECT COLUMN_NAME AS column_name,
                   DATA_TYPE AS data_type,
                   IS_NULLABLE AS is_nullable,
                   ORDINAL_POSITION AS ordinal_position
              FROM INFORMATION_SCHEMA.COLUMNS
             WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?
             ORDER BY ORDINAL_POSITION
            """,
            (FABRIC_SCHEMA, view),
        )
        return self._rows(cursor)

    @staticmethod
    def _verify_columns(
        view: str,
        observed: list[dict[str, Any]],
        required: tuple[str, ...],
    ) -> None:
        names = {item["column_name"] for item in observed}
        missing = sorted(set(required) - names)
        if missing:
            raise SourceError(
                "fabric_schema_mismatch",
                "Publish View에 계약 컬럼이 없습니다.",
                context={"view": view, "missing_columns": missing},
            )

    @staticmethod
    def _verify_types(view: str, observed: list[dict[str, Any]]) -> None:
        expected = EXPECTED_COLUMN_TYPES[view]
        incompatible = []
        for item in observed:
            column = str(item["column_name"])
            if column not in expected:
                continue
            actual = str(item["data_type"]).lower()
            if actual not in expected[column]:
                incompatible.append({"column": column, "actual_type": actual})
        if incompatible:
            raise SourceError(
                "fabric_schema_mismatch",
                "Publish View 계약 컬럼의 타입이 호환되지 않습니다.",
                context={"view": view, "incompatible_columns": incompatible},
            )

    @staticmethod
    def _select(cursor: Any, view: str, columns: tuple[str, ...]) -> list[dict[str, Any]]:
        projection = ", ".join(f"[{item}]" for item in columns)
        cursor.execute(f"SELECT {projection} FROM [{FABRIC_SCHEMA}].[{view}]")
        return FabricReader._rows(cursor)

    @staticmethod
    def _select_batches(
        cursor: Any,
        view: str,
        columns: tuple[str, ...],
        batch_ids: set[str],
    ) -> list[dict[str, Any]]:
        if not batch_ids:
            return []
        projection = ", ".join(f"[{item}]" for item in columns)
        rows: list[dict[str, Any]] = []
        ordered = sorted(batch_ids)
        for offset in range(0, len(ordered), 1000):
            chunk = ordered[offset : offset + 1000]
            placeholders = ", ".join("?" for _ in chunk)
            cursor.execute(
                f"SELECT {projection} FROM [{FABRIC_SCHEMA}].[{view}] "
                f"WHERE [batch_id] IN ({placeholders})",
                tuple(chunk),
            )
            rows.extend(FabricReader._rows(cursor))
        return rows

    def read(self) -> FabricSnapshot:
        try:
            with self._connect() as connection:
                cursor = connection.cursor()
                views = {
                    BATCH_VIEW: BATCH_COLUMNS,
                    CANDIDATE_VIEW: CANDIDATE_COLUMNS,
                    EVIDENCE_VIEW: EVIDENCE_COLUMNS,
                }
                schemas = {view: self._schema(cursor, view) for view in views}
                for view, columns in views.items():
                    self._verify_columns(view, schemas[view], columns)
                    self._verify_types(view, schemas[view])

                batches = self._select(cursor, BATCH_VIEW, BATCH_COLUMNS)
                batch_ids = {str(item["batch_id"]) for item in batches}
                candidates = self._select_batches(
                    cursor, CANDIDATE_VIEW, CANDIDATE_COLUMNS, batch_ids
                )
                evidence = self._select_batches(
                    cursor, EVIDENCE_VIEW, EVIDENCE_COLUMNS, batch_ids
                )
                return FabricSnapshot(schemas, batches, candidates, evidence)
        except SourceError:
            raise
        except Exception as exc:
            raise SourceError(
                "fabric_query_failed",
                "Fabric Publish View 조회에 실패했습니다.",
            ) from exc
