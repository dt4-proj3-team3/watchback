#!/usr/bin/env bash
set -euo pipefail

: "${IMAGE_TAG:?IMAGE_TAG가 필요합니다.}"

RESOURCE_GROUP="${AZURE_RESOURCE_GROUP:-4dt_3rdproject_team_3}"
ACR_NAME="${AZURE_ACR_NAME:-acrwatchbackdevbaursz7}"
BACKEND_APP="${AZURE_BACKEND_APP:-ca-watchback-api-dev}"
FRONTEND_APP="${AZURE_FRONTEND_APP:-ca-watchback-web-dev}"
HEALTH_TIMEOUT_SECONDS="${HEALTH_TIMEOUT_SECONDS:-300}"

registry_server="$ACR_NAME.azurecr.io"
backend_image="$registry_server/watchback-backend:$IMAGE_TAG"
frontend_image="$registry_server/watchback-frontend:$IMAGE_TAG"
old_backend_image="$(az containerapp show --resource-group "$RESOURCE_GROUP" --name "$BACKEND_APP" --query 'properties.template.containers[0].image' --output tsv)"
old_frontend_image="$(az containerapp show --resource-group "$RESOURCE_GROUP" --name "$FRONTEND_APP" --query 'properties.template.containers[0].image' --output tsv)"
rollback_required=false

rollback() {
  local exit_code="$?"
  if [[ "$exit_code" -ne 0 && "$rollback_required" == true ]]; then
    echo "배포 검증에 실패해 직전 이미지로 롤백합니다." >&2
    az containerapp update --resource-group "$RESOURCE_GROUP" --name "$BACKEND_APP" --image "$old_backend_image" --output none || true
    az containerapp update --resource-group "$RESOURCE_GROUP" --name "$FRONTEND_APP" --image "$old_frontend_image" --output none || true
  fi
  exit "$exit_code"
}
trap rollback EXIT

wait_for_revision() {
  local app_name="$1"
  local deadline=$((SECONDS + HEALTH_TIMEOUT_SECONDS))

  while (( SECONDS < deadline )); do
    local revision_name
    local state
    revision_name="$(az containerapp show --resource-group "$RESOURCE_GROUP" --name "$app_name" --query properties.latestRevisionName --output tsv)"
    state="$(az containerapp revision show \
      --resource-group "$RESOURCE_GROUP" \
      --name "$app_name" \
      --revision "$revision_name" \
      --query "join('|', [properties.provisioningState, properties.healthState, properties.runningState])" \
      --output tsv)"

    if [[ "$state" == "Provisioned|Healthy|RunningAtMaxScale" ]]; then
      echo "$app_name revision $revision_name: $state"
      return 0
    fi
    if [[ "$state" == Failed* || "$state" == *"|Unhealthy|"* ]]; then
      echo "$app_name revision $revision_name: $state" >&2
      return 1
    fi
    sleep 10
  done

  echo "$app_name revision이 ${HEALTH_TIMEOUT_SECONDS}초 안에 정상 상태가 되지 않았습니다." >&2
  return 1
}

verify_latest_traffic() {
  local app_name="$1"
  local revision_mode
  local latest_weight
  revision_mode="$(az containerapp show --resource-group "$RESOURCE_GROUP" --name "$app_name" --query properties.configuration.activeRevisionsMode --output tsv)"
  latest_weight="$(az containerapp show --resource-group "$RESOURCE_GROUP" --name "$app_name" --query 'properties.configuration.ingress.traffic[?latestRevision].weight | [0]' --output tsv)"

  if [[ "$revision_mode" != "Single" || "$latest_weight" != "100" ]]; then
    echo "$app_name 트래픽이 최신 단일 Revision에 100% 연결되지 않았습니다." >&2
    return 1
  fi
}

rollback_required=true
az containerapp update --resource-group "$RESOURCE_GROUP" --name "$BACKEND_APP" --image "$backend_image" --output none
az containerapp update --resource-group "$RESOURCE_GROUP" --name "$FRONTEND_APP" --image "$frontend_image" --output none

wait_for_revision "$BACKEND_APP"
wait_for_revision "$FRONTEND_APP"
verify_latest_traffic "$BACKEND_APP"
verify_latest_traffic "$FRONTEND_APP"

backend_url="https://$(az containerapp show --resource-group "$RESOURCE_GROUP" --name "$BACKEND_APP" --query properties.configuration.ingress.fqdn --output tsv)"
frontend_url="https://$(az containerapp show --resource-group "$RESOURCE_GROUP" --name "$FRONTEND_APP" --query properties.configuration.ingress.fqdn --output tsv)"
curl --fail --silent --show-error --retry 5 --retry-all-errors --retry-delay 5 "$backend_url/openapi.json" >/dev/null
curl --fail --silent --show-error --retry 5 --retry-all-errors --retry-delay 5 "$frontend_url/dashboard" >/dev/null

rollback_required=false
printf '{"image_tag":"%s","backend":"%s","frontend":"%s"}\n' "$IMAGE_TAG" "$backend_url" "$frontend_url"
