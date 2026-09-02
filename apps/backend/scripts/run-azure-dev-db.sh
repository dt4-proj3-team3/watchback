#!/usr/bin/env bash
set -euo pipefail

backend_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
key_vault_name="${WATCHBACK_KEY_VAULT_NAME:-kv-watchback-dev-baursz7}"
database_secret_name="${WATCHBACK_DATABASE_SECRET_NAME:-database-url}"
github_secret_name="${WATCHBACK_GITHUB_SECRET_NAME:-github-token}"
resource_group="${AZURE_RESOURCE_GROUP:-4dt_3rdproject_team_3}"
ai_deployment_record="${AZURE_AI_AGENT_DEPLOYMENT_NAME:-watchback-dev-ai-agent}"

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

if github_remediation_token="$(az keyvault secret show \
  --vault-name "$key_vault_name" \
  --name "$github_secret_name" \
  --query value \
  --output tsv 2>/dev/null)" && [[ -n "$github_remediation_token" ]]; then
  export GITHUB_REMEDIATION_TOKEN="$github_remediation_token"
else
  echo "Key Vault에서 GitHub 조치 토큰을 가져오지 못해 PR 조치 기능을 비활성화합니다." >&2
fi

if [[ -z "${AZURE_OPENAI_ENDPOINT:-}" || -z "${AZURE_OPENAI_DEPLOYMENT:-}" ]]; then
  if ai_endpoint="$(az deployment group show \
    --resource-group "$resource_group" \
    --name "$ai_deployment_record" \
    --query properties.outputs.endpoint.value \
    --output tsv 2>/dev/null)" && \
    ai_model_deployment="$(az deployment group show \
      --resource-group "$resource_group" \
      --name "$ai_deployment_record" \
      --query properties.outputs.deploymentName.value \
      --output tsv 2>/dev/null)" && \
    [[ -n "$ai_endpoint" && -n "$ai_model_deployment" ]]; then
    export AZURE_OPENAI_ENDPOINT="$ai_endpoint"
    export AZURE_OPENAI_DEPLOYMENT="$ai_model_deployment"
  else
    echo "Azure OpenAI 배포 정보를 찾지 못해 AI 검토 도우미를 비활성화합니다." >&2
  fi
fi

cd "$backend_dir"
export DATABASE_URL="$database_url"
exec .venv/bin/python -m uvicorn watchback_backend.main:app \
  --app-dir src \
  --host 127.0.0.1 \
  --port "${WATCHBACK_BACKEND_PORT:-8000}" \
  "$@"
