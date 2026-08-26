from __future__ import annotations

from typing import Any


class SyncError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.context = context or {}


class SourceError(SyncError):
    pass


class ContractError(SyncError):
    pass


class PersistenceError(SyncError):
    pass
