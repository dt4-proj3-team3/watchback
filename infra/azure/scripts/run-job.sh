#!/usr/bin/env bash
set -euo pipefail

if [[ "$#" -ne 1 ]]; then
  echo "사용법: $0 <job-name>" >&2
  exit 2
fi

RESOURCE_GROUP="${AZURE_RESOURCE_GROUP:-4dt_3rdproject_team_3}"
JOB_NAME="$1"
TIMEOUT_SECONDS="${JOB_TIMEOUT_SECONDS:-1800}"

execution_name="$(az containerapp job start \
  --resource-group "$RESOURCE_GROUP" \
  --name "$JOB_NAME" \
  --query name \
  --output tsv)"

if [[ -z "$execution_name" ]]; then
  echo "$JOB_NAME 실행 ID를 확인하지 못했습니다." >&2
  exit 1
fi

started_at="$(date +%s)"
while true; do
  status="$(az containerapp job execution show \
    --resource-group "$RESOURCE_GROUP" \
    --name "$JOB_NAME" \
    --job-execution-name "$execution_name" \
    --query 'properties.status' \
    --output tsv)"

  case "$status" in
    Succeeded)
      printf '{"job":"%s","execution":"%s","status":"Succeeded"}\n' "$JOB_NAME" "$execution_name"
      exit 0
      ;;
    Failed|Stopped|Degraded)
      printf '{"job":"%s","execution":"%s","status":"%s"}\n' "$JOB_NAME" "$execution_name" "$status" >&2
      exit 1
      ;;
  esac

  if (( $(date +%s) - started_at >= TIMEOUT_SECONDS )); then
    echo "$JOB_NAME 실행이 ${TIMEOUT_SECONDS}초 안에 끝나지 않았습니다: $execution_name" >&2
    exit 1
  fi
  sleep 10
done
