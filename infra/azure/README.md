# Azure 개발 환경

Watchback의 개발용 PostgreSQL, Container Apps와 수동 Job을 Bicep으로 관리한다. 대상 구독과 리소스 그룹은 다음과 같다.

| 항목 | 값 |
| --- | --- |
| 구독 | `대한상공회의소 Data School` (`27db5ec6-d206-4028-b5e1-6004dca5eeef`) |
| 리소스 그룹 | `4dt_3rdproject_team_3` |
| 리전 | `koreacentral` |
| 환경 | `dev` |

## 배포 범위

- Azure Database for PostgreSQL Flexible Server 16
- Azure Container Registry Basic
- Azure Key Vault와 런타임·CD용 사용자 할당 Managed Identity
- Azure Container Apps Frontend·Backend
- DB 초기화 및 Dependabot 동기화 Container Apps Job
- Log Analytics Workspace와 Application Insights

Frontend의 재검토 목록·상세는 기본 `db` 모드에서 Backend API를 사용한다. Bicep은 S1 기준 조직·사용자 ID를 Frontend Route Handler에 전달하며, 설정에서 명시적으로 Demo를 선택할 수 있다. 대시보드·저장소·자동조치 정책은 계속 Demo 기반 읽기 전용 `UI Preview`다. Gold Sync Job은 별도 배포 범위이며 `modules/container-app-job.bicep`을 재사용한다.

## 사전 조건

- Azure CLI 로그인과 Bicep CLI
- GitHub CLI와 jq(CD Repository variables 설정 시)
- 현재 구독에서 리소스·역할 할당을 생성할 권한
- `Dependabot alerts: read` 권한이 있는 `GITHUB_TOKEN`
- Git, curl, OpenSSL

토큰 없이 배포하면 Dependabot Job만 생략한다. 비밀값은 파라미터 파일이나 Git에 저장하지 않는다.

## 애플리케이션 자동 배포

`main`에서 Backend, Frontend 또는 데모 데이터가 변경되면 GitHub Actions가 두 이미지를 전체 커밋 SHA 태그로 ACR에 게시하고 기존 Container Apps를 갱신한다. DB Migration, Seed와 Sync Job은 자동 실행하지 않는다.

Azure 로그인에는 장기 Client Secret 대신 `main` 브랜치만 신뢰하는 OIDC와 전용 Managed Identity를 사용한다. 최초 Bicep 배포 후 다음 Repository variables를 설정한다.

```bash
az deployment group create \
  --resource-group 4dt_3rdproject_team_3 \
  --name watchback-dev-app-cd \
  --template-file infra/azure/app-cd.bicep

deployment_outputs="$(az deployment group show \
  --resource-group 4dt_3rdproject_team_3 \
  --name watchback-dev-app-cd \
  --query properties.outputs \
  --output json)"

gh variable set AZURE_CLIENT_ID \
  --body "$(jq -r '.cdClientId.value' <<<"$deployment_outputs")"
gh variable set AZURE_TENANT_ID \
  --body "$(jq -r '.tenantId.value' <<<"$deployment_outputs")"
gh variable set AZURE_SUBSCRIPTION_ID \
  --body "$(jq -r '.subscriptionId.value' <<<"$deployment_outputs")"
```

Workflow는 새 Revision이 `Provisioned`, `Healthy`, `RunningAtMaxScale`인지 확인하고 Backend `/openapi.json`과 Frontend `/dashboard`를 호출한다. 실패하면 두 앱을 직전 이미지로 롤백한다. GitHub Actions의 `Deploy development apps`에서 수동 재실행할 수 있다.

특정 ACR 태그로 수동 배포하거나 롤백할 때는 Azure 로그인 후 같은 스크립트를 사용한다.

```bash
az acr repository show-tags \
  --name acrwatchbackdevbaursz7 \
  --repository watchback-backend \
  --orderby time_desc \
  --top 10 \
  --output table

IMAGE_TAG='<commit-sha-or-previous-tag>' infra/azure/scripts/deploy-app-images.sh
```

## 배포

먼저 로컬 검증을 실행한다.

```bash
az bicep build --file infra/azure/foundation.bicep
az bicep build --file infra/azure/main.bicep
az bicep build --file infra/azure/app-cd.bicep
```

작업 트리의 검증된 커밋을 이미지 태그로 사용한다. 전체 배포는 다음 명령으로 실행한다.

```bash
export GITHUB_TOKEN='...'
infra/azure/scripts/deploy-dev.sh
unset GITHUB_TOKEN
```

스크립트는 다음 순서로 동작한다.

1. ACR과 Key Vault를 배포한다.
2. PostgreSQL 비밀번호를 처음 한 번 생성해 Key Vault에 저장한다.
3. 토큰이 있으면 Key Vault에 저장한다.
4. Backend, Frontend, Dependabot Worker 이미지를 ACR에서 빌드한다.
5. PostgreSQL, Container Apps, Job과 로그 리소스를 배포한다.
6. 개발자 IP와 Azure 서비스 허용 규칙으로 PostgreSQL 접근을 제한한다.
7. GitHub Actions용 OIDC Identity와 최소 배포 권한을 구성한다.

기본 이미지 태그는 현재 Git commit SHA 12자리다. 다른 태그가 필요하면 `IMAGE_TAG`를 명시한다. 개발자 공인 IP 자동 조회가 불가능하면 `DEVELOPER_IP`를 지정한다.

## Migration과 동기화

DB 초기화 Job을 먼저 실행한다.

```bash
infra/azure/scripts/run-job.sh caj-watchback-db-init-dev
```

Dependabot Job이 배포된 경우 두 번 연속 실행해 두 번째 결과의 신규·원본 갱신 건수가 0인지 확인한다.

```bash
infra/azure/scripts/run-job.sh caj-watchback-dependabot-dev
infra/azure/scripts/run-job.sh caj-watchback-dependabot-dev
```

실행 로그는 다음과 같이 확인한다.

```bash
az containerapp job execution list \
  --resource-group 4dt_3rdproject_team_3 \
  --name caj-watchback-dependabot-dev \
  --output table

az containerapp logs show \
  --resource-group 4dt_3rdproject_team_3 \
  --name ca-watchback-api-dev \
  --tail 50
```

기본 상태 검증은 다음 명령을 사용한다.

```bash
infra/azure/scripts/verify-dev.sh
```

## 재배포와 방화벽

PostgreSQL 방화벽에는 로컬 접속을 위한 개발자 공인 IP와 Container Apps·Job 접속을 위한 Azure 서비스 허용 규칙을 둔다. 따라서 Container Apps의 변동 가능한 outbound IP를 개별 등록하지 않는다. 개발자 IP가 바뀌면 `DEVELOPER_IP`를 지정해 다시 배포한다.

Azure 서비스 허용 규칙은 다른 Azure 고객의 리소스에서도 서버에 접속을 시도할 수 있는 넓은 규칙이다. 실제 접속에는 PostgreSQL 인증과 TLS가 필요하지만 개발 환경에서만 사용하며, 운영 환경에서는 PostgreSQL을 Private Access로 구성한다.

## 비용과 정리

주요 지속 비용은 PostgreSQL `Standard_B1ms` 32GiB, ACR Basic, Log Analytics 수집량과 Frontend·Backend의 상시 최소 Replica 1개다. Job은 실행량에 따라 비용이 발생한다.

콜드스타트보다 비용 절감이 우선이면 `infra/azure/main.bicep`의 두 `minReplicas`를 0으로 되돌리고 Bicep을 재배포한다.

개발을 중단할 때 PostgreSQL을 일시 정지할 수 있다.

```bash
az postgres flexible-server stop \
  --resource-group 4dt_3rdproject_team_3 \
  --name "$(az deployment group show --resource-group 4dt_3rdproject_team_3 --name watchback-dev --query 'properties.outputs.postgresName.value' --output tsv)"
```

리소스 그룹은 다른 팀 리소스와 공유하므로 삭제하지 않는다. 정리 전 `project=watchback`, `environment=dev` 태그로 대상을 확인한 뒤 Watchback 리소스만 개별 삭제한다.
