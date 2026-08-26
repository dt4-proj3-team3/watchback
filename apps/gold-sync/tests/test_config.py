from __future__ import annotations

from watchback_gold_sync.config import Settings


def test_runtime_access_token_is_optional_and_hidden_from_repr(monkeypatch) -> None:
    monkeypatch.setenv("FABRIC_SQL_SERVER", "fabric.example")
    monkeypatch.setenv("FABRIC_SQL_DATABASE", "lakehouse")
    monkeypatch.setenv("DATABASE_URL", "postgresql://database.example/watchback")
    monkeypatch.setenv("FABRIC_SQL_ACCESS_TOKEN", "short-lived-secret")

    settings = Settings.from_environment()

    assert settings.fabric_sql_access_token == "short-lived-secret"
    assert "short-lived-secret" not in repr(settings)
