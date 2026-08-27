#!/usr/bin/env bash
set -euo pipefail

EXPECTED_SUBSCRIPTION_ID="27db5ec6-d206-4028-b5e1-6004dca5eeef"
RESOURCE_GROUP="${AZURE_RESOURCE_GROUP:-4dt_3rdproject_team_3}"
LOCATION="${AZURE_LOCATION:-koreacentral}"
FOUNDATION_DEPLOYMENT="watchback-dev-foundation"
MAIN_DEPLOYMENT="${AZURE_DEPLOYMENT_NAME:-watchback-dev}"
APP_CD_DEPLOYMENT="${AZURE_APP_CD_DEPLOYMENT_NAME:-watchback-dev-app-cd}"
REPOSITORY_ROOT="$(git rev-parse --show-toplevel)"
IMAGE_TAG="${IMAGE_TAG:-$(git rev-parse --short=12 HEAD)}"
frontend_context=""
cleanup() {
  if [[ -n "$frontend_context" && -d "$frontend_context" ]]; then
    rm -rf "$frontend_context"
  fi
}
trap cleanup EXIT

for command_name in az curl git openssl; do
  command -v "$command_name" >/dev/null || {
    echo "$command_name 명령이 필요합니다." >&2
    exit 1
  }
done

current_subscription="$(az account show --query id --output tsv)"
if [[ "$current_subscription" != "$EXPECTED_SUBSCRIPTION_ID" ]]; then
  echo "예상 구독이 아닙니다: $current_subscription" >&2
  exit 1
fi

deployer_object_id="$(az ad signed-in-user show --query id --output tsv)"
developer_ip="${DEVELOPER_IP:-$(curl --fail --silent --show-error https://api.ipify.org)}"

az deployment group create \
  --resource-group "$RESOURCE_GROUP" \
  --name "$FOUNDATION_DEPLOYMENT" \
  --template-file "$REPOSITORY_ROOT/infra/azure/foundation.bicep" \
  --parameters location="$LOCATION" deployerObjectId="$deployer_object_id" \
  --output none

registry_name="$(az deployment group show \
  --resource-group "$RESOURCE_GROUP" \
  --name "$FOUNDATION_DEPLOYMENT" \
  --query 'properties.outputs.registryName.value' \
  --output tsv)"
key_vault_name="$(az deployment group show \
  --resource-group "$RESOURCE_GROUP" \
  --name "$FOUNDATION_DEPLOYMENT" \
  --query 'properties.outputs.keyVaultName.value' \
  --output tsv)"

if ! postgres_password="$(az keyvault secret show \
  --vault-name "$key_vault_name" \
  --name postgres-admin-password \
  --query value \
  --output tsv 2>/dev/null)"; then
  postgres_password="$(openssl rand -hex 24)"
  for attempt in {1..12}; do
    if az keyvault secret set \
      --vault-name "$key_vault_name" \
      --name postgres-admin-password \
      --value "$postgres_password" \
      --output none 2>/dev/null; then
      break
    fi
    if [[ "$attempt" -eq 12 ]]; then
      echo "Key Vault 역할 전파 후에도 PostgreSQL 비밀번호를 저장하지 못했습니다." >&2
      exit 1
    fi
    sleep 10
  done
fi

deploy_dependabot_job=false
if [[ -n "${GITHUB_TOKEN:-}" ]]; then
  az keyvault secret set \
    --vault-name "$key_vault_name" \
    --name github-token \
    --value "$GITHUB_TOKEN" \
    --output none
  deploy_dependabot_job=true
else
  echo "GITHUB_TOKEN이 없어 Dependabot Sync Job 배포와 Live 검증을 생략합니다." >&2
fi

az acr build --registry "$registry_name" --image "watchback-backend:$IMAGE_TAG" \
  --file "$REPOSITORY_ROOT/apps/backend/Dockerfile" "$REPOSITORY_ROOT/apps/backend"
az acr build --registry "$registry_name" --image "watchback-dependabot-sync:$IMAGE_TAG" \
  --file "$REPOSITORY_ROOT/apps/dependabot-sync/Dockerfile" "$REPOSITORY_ROOT/apps/dependabot-sync"

frontend_context="$(mktemp -d)"
mkdir -p "$frontend_context/apps" "$frontend_context/data"
cp -R "$REPOSITORY_ROOT/apps/frontend" "$frontend_context/apps/frontend"
cp -R "$REPOSITORY_ROOT/data/demo" "$frontend_context/data/demo"
cp "$REPOSITORY_ROOT/.dockerignore" "$frontend_context/.dockerignore"
az acr build --registry "$registry_name" --image "watchback-frontend:$IMAGE_TAG" \
  --file "$frontend_context/apps/frontend/Dockerfile" "$frontend_context"

az deployment group create \
  --resource-group "$RESOURCE_GROUP" \
  --name "$MAIN_DEPLOYMENT" \
  --template-file "$REPOSITORY_ROOT/infra/azure/main.bicep" \
  --parameters \
    location="$LOCATION" \
    imageTag="$IMAGE_TAG" \
    developerIp="$developer_ip" \
    deployDependabotJob="$deploy_dependabot_job" \
    postgresAdminPassword="$postgres_password" \
  --output none

az deployment group create \
  --resource-group "$RESOURCE_GROUP" \
  --name "$APP_CD_DEPLOYMENT" \
  --template-file "$REPOSITORY_ROOT/infra/azure/app-cd.bicep" \
  --parameters location="$LOCATION" \
  --output none

echo "Azure 개발 환경 배포가 완료되었습니다. imageTag=$IMAGE_TAG"
az deployment group show \
  --resource-group "$RESOURCE_GROUP" \
  --name "$MAIN_DEPLOYMENT" \
  --query 'properties.outputs.{frontend:frontendUrl.value,backend:backendUrl.value,databaseInitJob:databaseInitJobName.value,dependabotJob:dependabotJobName.value}' \
  --output json
