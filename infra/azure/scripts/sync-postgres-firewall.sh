#!/usr/bin/env bash
set -euo pipefail

RESOURCE_GROUP="${AZURE_RESOURCE_GROUP:-4dt_3rdproject_team_3}"
DEPLOYMENT_NAME="${AZURE_DEPLOYMENT_NAME:-watchback-dev}"

POSTGRES_NAME="$(az deployment group show \
  --resource-group "$RESOURCE_GROUP" \
  --name "$DEPLOYMENT_NAME" \
  --query 'properties.outputs.postgresName.value' \
  --output tsv)"

temporary_file="$(mktemp)"
trap 'rm -f "$temporary_file"' EXIT

for app_name in ca-watchback-api-dev ca-watchback-web-dev; do
  az containerapp show \
    --resource-group "$RESOURCE_GROUP" \
    --name "$app_name" \
    --query 'properties.outboundIpAddresses[]' \
    --output tsv >>"$temporary_file"
done

for job_name in caj-watchback-db-init-dev caj-watchback-dependabot-dev; do
  if az containerapp job show --resource-group "$RESOURCE_GROUP" --name "$job_name" --output none 2>/dev/null; then
    az containerapp job show \
      --resource-group "$RESOURCE_GROUP" \
      --name "$job_name" \
      --query 'properties.outboundIpAddresses[]' \
      --output tsv >>"$temporary_file"
  fi
done

outbound_ips=()
while IFS= read -r ip_address; do
  outbound_ips+=("$ip_address")
done < <(tr '\t' '\n' <"$temporary_file" | sed '/^$/d' | sort -u)
if [[ "${#outbound_ips[@]}" -eq 0 ]]; then
  echo "Container Apps outbound IP를 찾지 못했습니다." >&2
  exit 1
fi

previous_rules=()
while IFS= read -r rule_name; do
  [[ -n "$rule_name" ]] && previous_rules+=("$rule_name")
done < <(az postgres flexible-server firewall-rule list \
  --resource-group "$RESOURCE_GROUP" \
  --name "$POSTGRES_NAME" \
  --query "[?starts_with(name, 'watchback-aca-')].name" \
  --output tsv)

for rule_name in "${previous_rules[@]}"; do
  az postgres flexible-server firewall-rule delete \
    --resource-group "$RESOURCE_GROUP" \
    --name "$POSTGRES_NAME" \
    --rule-name "$rule_name" \
    --yes \
    --output none
done

index=1
for ip_address in "${outbound_ips[@]}"; do
  rule_name="$(printf 'watchback-aca-%03d' "$index")"
  az postgres flexible-server firewall-rule create \
    --resource-group "$RESOURCE_GROUP" \
    --name "$POSTGRES_NAME" \
    --rule-name "$rule_name" \
    --start-ip-address "$ip_address" \
    --end-ip-address "$ip_address" \
    --output none
  index=$((index + 1))
done

echo "PostgreSQL 방화벽에 Container Apps outbound IP ${#outbound_ips[@]}개를 반영했습니다."
