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
- Azure Key Vault와 사용자 할당 Managed Identity
- Azure Container Apps Frontend·Backend
- DB 초기화 및 Dependabot 동기화 Container Apps Job
- Log Analytics Workspace와 Application Insights

Frontend는 현재 `data/demo`를 사용하며 Backend의 DB 조회 API와 연결되지 않는다. Gold Sync Job도 구현 전이므로 배포하지 않는다. `modules/container-app-job.bicep`은 후속 Gold Sync Worker에서도 재사용할 수 있다.

## 사전 조건

- Azure CLI 로그인과 Bicep CLI
- 현재 구독에서 리소스·역할 할당을 생성할 권한
- `Dependabot alerts: read` 권한이 있는 `GITHUB_TOKEN`
- Git, curl, OpenSSL

토큰 없이 배포하면 Dependabot Job만 생략한다. 비밀값은 파라미터 파일이나 Git에 저장하지 않는다.

## 배포

먼저 로컬 검증을 실행한다.

```bash
az bicep build --file infra/azure/foundation.bicep
az bicep build --file infra/azure/main.bicep
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
6. 현재 Container Apps outbound IP만 PostgreSQL 방화벽에 반영한다.

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

Container Apps Consumption 환경의 outbound IP는 바뀔 수 있다. `deploy-dev.sh`는 매번 실제 IP를 다시 조회하고 `watchback-aca-*` 방화벽 규칙만 교체한다. 개발자 IP가 바뀌면 `DEVELOPER_IP`를 지정해 다시 배포한다.

`0.0.0.0` Azure 전체 허용 규칙은 만들지 않는다. 이 공개·제한형 구성이 개발 범위를 넘어서면 PostgreSQL과 Container Apps를 VNet 사설 연결로 이전한다.

## 비용과 정리

주요 지속 비용은 PostgreSQL `Standard_B1ms` 32GiB, ACR Basic, Log Analytics 수집량이다. Container Apps는 최소 Replica가 0이지만 요청과 Job 실행량에 따라 비용이 발생한다.

개발을 중단할 때 PostgreSQL을 일시 정지할 수 있다.

```bash
az postgres flexible-server stop \
  --resource-group 4dt_3rdproject_team_3 \
  --name "$(az deployment group show --resource-group 4dt_3rdproject_team_3 --name watchback-dev --query 'properties.outputs.postgresName.value' --output tsv)"
```

리소스 그룹은 다른 팀 리소스와 공유하므로 삭제하지 않는다. 정리 전 `project=watchback`, `environment=dev` 태그로 대상을 확인한 뒤 Watchback 리소스만 개별 삭제한다.
