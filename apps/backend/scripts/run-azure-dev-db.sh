#!/usr/bin/env bash
set -euo pipefail

backend_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
key_vault_name="${WATCHBACK_KEY_VAULT_NAME:-kv-watchback-dev-baursz7}"
database_secret_name="${WATCHBACK_DATABASE_SECRET_NAME:-database-url}"

if ! command -v az >/dev/null 2>&1; then
  echo "Azure CLI가 필요합니다." >&2
  exit 1
fi

if ! az account show >/dev/null 2>&1; then
  echo "Azure CLI 로그인이 필요합니다. az login을 먼저 실행하세요." >&2
  exit 1
fi

if ! database_url="$(az keyvault secret show \
  --vault-name "$key_vault_name" \
  --name "$database_secret_name" \
  --query value \
  --output tsv 2>/dev/null)" || [[ -z "$database_url" ]]; then
  echo "Key Vault에서 Azure 개발 DB 접속정보를 가져오지 못했습니다." >&2
  exit 1
fi

cd "$backend_dir"
export DATABASE_URL="$database_url"
exec .venv/bin/python -m uvicorn watchback_backend.main:app \
  --app-dir src \
  --host 127.0.0.1 \
  --port "${WATCHBACK_BACKEND_PORT:-8000}" \
  "$@"
