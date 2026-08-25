#!/usr/bin/env bash
set -euo pipefail

RESOURCE_GROUP="${AZURE_RESOURCE_GROUP:-4dt_3rdproject_team_3}"
DEPLOYMENT_NAME="${AZURE_DEPLOYMENT_NAME:-watchback-dev}"

output() {
  az deployment group show \
    --resource-group "$RESOURCE_GROUP" \
    --name "$DEPLOYMENT_NAME" \
    --query "properties.outputs.$1.value" \
    --output tsv
}

backend_url="$(output backendUrl)"
frontend_url="$(output frontendUrl)"
postgres_name="$(output postgresName)"

curl --fail --silent --show-error "$backend_url/openapi.json" >/dev/null
curl --fail --silent --show-error "$backend_url/docs" >/dev/null
curl --fail --silent --show-error "$frontend_url/dashboard" >/dev/null

if [[ "$(az acr show --name "$(output registryName)" --query adminUserEnabled --output tsv)" != "false" ]]; then
  echo "ACR 관리자 계정이 비활성화되어 있지 않습니다." >&2
  exit 1
fi

if az postgres flexible-server firewall-rule list \
  --resource-group "$RESOURCE_GROUP" \
  --name "$postgres_name" \
  --query "[?startIpAddress=='0.0.0.0' && endIpAddress=='0.0.0.0'] | length(@)" \
  --output tsv | grep -qv '^0$'; then
  echo "모든 Azure 서비스 허용 방화벽 규칙이 존재합니다." >&2
  exit 1
fi

printf '{"backend":"%s","frontend":"%s","acr_admin":false,"broad_azure_firewall":false}\n' \
  "$backend_url" "$frontend_url"
