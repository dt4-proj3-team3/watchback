# Fabric API 개발 워크플로

이 문서는 GitHub의 로컬 소스를 원본으로 두고 Microsoft Fabric REST API로 Notebook과 Data Pipeline을 생성·배포·실행하는 방법을 설명한다. 팀원과 에이전트는 Fabric 항목을 변경하기 전에 이 문서를 기준으로 작업한다.

## 운영 원칙

```text
GitHub Issue
→ 작업 브랜치에서 로컬 소스 수정
→ Fabric 개발 워크스페이스에 API 배포
→ 원격 실행과 결과 검증
→ 커밋·PR
```

- GitHub의 로컬 파일을 코드 원본으로 사용한다.
- Fabric 워크스페이스는 실행과 검증 환경으로 사용한다.
- Fabric Git Integration은 이 워크플로의 필수 요소가 아니다.
- Fabric 웹 편집기와 로컬에서 같은 항목을 동시에 수정하지 않는다.
- 운영 데이터가 있는 Lakehouse는 Notebook 배포와 별개로 보존한다.
- 액세스 토큰과 자격 증명은 파일, 셀 출력, 로그와 Git에 남기지 않는다.

Fabric Item API의 정의 갱신은 원격 내용을 교체한다. 웹 편집기에 저장되지 않은 변경이 있으면 충돌 선택 화면이 나타날 수 있고, 편집 중인 내용이 없으면 API 변경이 자동 반영될 수 있다.

## 저장소의 Fabric 소스

Fabric에 배포할 항목은 작업 성격에 따라 `fabric/workspace/` 아래에 둔다.

```text
fabric/workspace/
├── ingestion/          # 외부 위험 데이터 수집
├── transformation/     # Bronze·Silver·Gold 변환
├── analysis/           # 위험 변화 분석
├── migrations/         # Lakehouse 스키마 변경 Notebook
├── validation/         # 데이터 품질·E2E 검증
└── orchestration/      # Data Pipeline
```

Notebook은 다음 형식 중 하나를 원본으로 사용할 수 있다.

- Jupyter 형식: `name.ipynb`
- Fabric Git Source 형식: `name.Notebook/notebook-content.py`

한 항목을 두 형식으로 중복 관리하지 않는다. API 중심 작업에서 `.platform`은 필수가 아니다. 기존 Fabric Git Source 항목을 그대로 이관하거나 `fabric-cicd`를 사용할 때는 `.platform`을 함께 보존한다.

## 준비와 인증

로컬 개발자는 Azure CLI로 자신의 Microsoft Entra 계정을 인증한다.

```bash
az login
az account show
```

Fabric API 토큰은 명령 실행 시 발급받고 저장하지 않는다.

```bash
FABRIC_TOKEN=$(az account get-access-token \
  --resource https://api.fabric.microsoft.com \
  --query accessToken \
  --output tsv)
```

GitHub PAT는 Fabric REST API 인증 수단이 아니다. 팀원이 개인 토큰이나 Azure CLI 인증 정보를 공유하지 않는다.

## 대상 확인

배포 전에 워크스페이스와 항목을 이름으로 조회해 정확한 ID를 확인한다. 이름만 보고 다른 워크스페이스의 항목을 갱신하지 않는다.

```bash
curl --silent --show-error \
  --header "Authorization: Bearer $FABRIC_TOKEN" \
  "https://api.fabric.microsoft.com/v1/workspaces"
```

```bash
curl --silent --show-error \
  --header "Authorization: Bearer $FABRIC_TOKEN" \
  "https://api.fabric.microsoft.com/v1/workspaces/$WORKSPACE_ID/items?type=Notebook"
```

워크스페이스 ID와 Item ID는 비밀정보가 아니지만 환경에 종속된다. Notebook 코드에 하드코딩하지 않고 배포 명령이나 환경별 설정으로 전달한다.

## Notebook 생성과 갱신

### 최초 생성

새 Notebook은 Fabric 웹에서 먼저 만들지 않아도 된다. 로컬 `.ipynb`를 Base64로 인코딩하고 Create Notebook API에 전달한다.

```bash
NOTEBOOK_PAYLOAD=$(base64 < "$NOTEBOOK_PATH" | tr -d '\n')

jq --null-input \
  --arg name "$NOTEBOOK_NAME" \
  --arg payload "$NOTEBOOK_PAYLOAD" \
  '{
    displayName: $name,
    definition: {
      format: "ipynb",
      parts: [{
        path: "notebook-content.ipynb",
        payload: $payload,
        payloadType: "InlineBase64"
      }]
    }
  }' |
curl --silent --show-error \
  --request POST \
  --header "Authorization: Bearer $FABRIC_TOKEN" \
  --header "Content-Type: application/json" \
  --data-binary @- \
  "https://api.fabric.microsoft.com/v1/workspaces/$WORKSPACE_ID/notebooks"
```

응답이 `202 Accepted`이면 `Location`, `x-ms-operation-id`, `Retry-After` 헤더를 확인하고 장기 실행 작업이 끝날 때까지 조회한다. 생성 결과에서 발급된 Item ID를 이후 갱신과 실행에 사용한다.

### 기존 항목 갱신

기존 Notebook은 먼저 최신 원격 정의와 Item ID를 확인한 뒤 Update Definition API로 갱신한다.

```text
POST /v1/workspaces/{workspaceId}/notebooks/{notebookId}/updateDefinition
```

Jupyter 원본에는 `format: ipynb`과 `notebook-content.ipynb`를 사용한다. Fabric Git Source 원본에는 `format: fabricGitSource`와 언어에 맞는 `notebook-content.py` 등의 파일을 사용한다.

원격 정의를 로컬 원본으로 가져오는 경우 다음 API를 사용한다.

```text
POST /v1/workspaces/{workspaceId}/notebooks/{notebookId}/getDefinition?format=ipynb
```

원격에서 내려받은 실행 출력과 환경 메타데이터를 무조건 로컬 원본에 덮어쓰지 않는다. 코드와 필요한 Notebook 메타데이터만 검토해 반영한다.

## Notebook 실행과 결과

배포가 성공한 후 Job API로 Notebook을 실행한다.

```text
POST /v1/workspaces/{workspaceId}/notebooks/{notebookId}/jobs/execute/instances?beta=false
```

`202 Accepted` 응답의 `Location`, `Retry-After`, Job ID를 기록한다. `Retry-After`보다 이르게 반복 조회하지 않고, Job이 종결 상태가 될 때까지 조회한다.

```text
GET /v1/workspaces/{workspaceId}/notebooks/{notebookId}/jobs/execute/instances/{jobInstanceId}?beta=false
```

최소 확인 항목은 다음과 같다.

- `status`: `Completed` 여부
- `failureReason`: 실패 원인
- `startTimeUtc`, `endTimeUtc`: 실행 구간
- `properties.exitValue`: Notebook이 반환한 값
- 실행 Snapshot과 Spark 모니터링 링크

`print()`는 실행 로그 확인에 사용한다. 자동화가 읽을 작은 결과는 마지막 실행 셀에서 `notebookutils.notebook.exit()`로 반환한다.

```python
import json

run_result = {
    "status": "ok",
    "row_count": row_count,
    "invalid_count": invalid_count,
    "output_table": "silver_epss",
}

print(run_result)
notebookutils.notebook.exit(json.dumps(run_result))
```

JSON은 필수 형식이 아니지만 여러 값을 기계적으로 파싱할 때 사용한다. 대량 데이터와 상세 로그를 `exitValue`로 반환하지 않는다. 데이터는 Lakehouse에 저장하고 결과에는 상태, 건수, 출력 위치와 검증 요약만 담는다.

## Data Pipeline

Data Pipeline도 Item Definition API로 생성·조회·갱신할 수 있다. 정의의 주요 부분은 다음과 같다.

```text
pipeline-content.json   # Activity와 의존 관계
.schedules              # 실행 일정
.platform               # 항목 메타데이터
```

단순한 Pipeline이나 기존 정의의 반복 배포는 API로 처리할 수 있다. Activity 종류가 많고 조건 분기가 복잡한 Pipeline은 Fabric UI에서 뼈대를 만들고, 내보낸 정의를 Git에서 검토한 뒤 API로 배포하는 편이 안전하다.

Pipeline은 다음 API로 원격 실행하고 Job 상태를 조회한다.

```text
POST /v1/workspaces/{workspaceId}/dataPipelines/{pipelineId}/jobs/execute/instances
```

Notebook Activity의 반환값은 후속 조건과 입력으로 사용할 수 있다. 데이터 자체보다 상태와 품질 검증 결과를 전달한다.

## 스키마와 마이그레이션

현재 Bronze·Silver·Gold·App 계약은 `docs/contracts/`의 계층별 문서에서 관리한다. 실행 가능한 DDL과 적용 순서는 `fabric/workspace/migrations/`의 Migration Notebook에서 관리하며, 별도의 스키마 코드 사본을 만들지 않는다.

```text
docs/contracts/
├── bronze/
├── silver/
├── gold/
└── app/

fabric/workspace/migrations/
├── 0001-baseline.ipynb
├── 0002-add-epss-score-date.ipynb
└── 0003-add-vulnerability-index.ipynb
```

- 파일명은 `NNNN-kebab-case.ipynb` 형식을 사용한다.
- `0001-baseline`은 기존 Lakehouse의 기준 스키마를 기록한다.
- 이후 변경은 번호 순서대로 한 번씩 적용한다.
- Migration Notebook은 Spark의 `spark.sql()`로 Lakehouse DDL을 실행한다. 읽기 전용 SQL Analytics Endpoint에서 마이그레이션하지 않는다.
- 이미 적용된 버전은 Lakehouse의 `_schema_migrations` 테이블에서 확인한다.
- 모든 DDL이 성공한 뒤 버전, 이름, 적용 시각과 checksum을 기록한다.
- 여러 DDL이 하나의 트랜잭션으로 묶인다고 가정하지 않고 재실행 가능하게 작성한다.
- 스키마 변경은 Migration Notebook과 관련 계약 문서를 같은 PR에서 갱신한다.

Migration Notebook도 일반 Notebook과 동일하게 API로 배포하고 Job API로 실행한다. 완료 후 Job 상태와 반환값뿐 아니라 대상 테이블의 컬럼·타입·null·키와 기존 데이터 호환성을 검증한다.

## 데이터 변경 검증

API 성공은 데이터가 올바르다는 뜻이 아니다. 수집·변환 Notebook은 다음을 별도로 확인한다.

- 기준 시점과 입력 파일
- 입력·출력 건수
- 키와 필드 매핑
- 누락, 중복과 타입
- reject 또는 invalid 건수와 샘플
- 재실행 시 중복 생성 여부
- Silver·Gold 스키마와 소비자 영향

Silver와 Gold에서는 JSON 자동 추론과 상시 `overwriteSchema`에 의존하지 않는다. 명시적 스키마를 적용하고, 스키마 변경은 관련 계약과 소비자 영향을 함께 검토한다.

## 협업과 안전

- 공유 워크스페이스의 같은 Item을 여러 사람이 동시에 배포하지 않는다.
- API 배포 전에 현재 원격 정의와 로컬 변경 대상을 확인한다.
- 실행 중인 Pipeline과 스케줄이 참조하는 Item은 ID와 의존성을 확인한 뒤 변경한다.
- 실험 항목은 이름으로 구분하고 운영 Pipeline에 연결하지 않는다.
- 삭제보다 보관 폴더 이동과 정의 백업을 우선한다.
- 배포·실행 결과에는 워크스페이스 이름, Item 이름과 ID, Job 또는 Operation ID, 최종 상태를 기록한다.
- 원격 생성·수정·실행·삭제는 사용자가 요청한 범위에서만 수행한다.

## 작업 완료 기준

Fabric 변경은 다음 조건을 모두 확인해야 완료로 보고한다.

1. 정확한 워크스페이스와 Item을 대상으로 했다.
2. Create 또는 Update 장기 실행 작업이 `Succeeded`로 끝났다.
3. 실행이 필요한 변경은 Job이 `Completed`로 끝났다.
4. `failureReason`과 반환값을 확인했다.
5. 데이터 변경은 건수·스키마·누락·중복·재실행 결과를 검증했다.
6. 로컬 원본과 원격 배포 대상의 관계를 기록했다.
