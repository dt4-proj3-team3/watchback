"""조직의 Dependabot Alert를 운영 DB에 동기화하는 Worker."""

from .service import run_sync

__all__ = ["run_sync"]
