# Gold Publish Sync Worker

Fabric Lakehouse SQL Analytics Endpoint의 완료된 Gold Publish View를 읽어 PostgreSQL Web 운영 DB에 Batch 단위로 반영하는 독립 CLI Worker다. Backend 패키지를 런타임에 import하지 않는다.

S1 Candidate는 CVE 기준이다. `cve_id`는 필수이고 `ghsa_id`는 선택 보조 식별자다. CVE가 없는 GHSA-only Candidate는 계약 오류로 처리한다.

## 입력

- Lakehouse: `watchback_lakehouse_dev_v2`
- Schema: `gold`
- `publish_rereview_batch`
- `publish_rereview_candidate`
- `publish_rereview_candidate_evidence`

세 View의 계약은 [`docs/contracts/app/gold-rereview-publish.md`](../../docs/contracts/app/gold-rereview-publish.md)를 따른다. View가 `completed` Batch만 제공하므로 Worker는 별도 상태를 추론하지 않는다.

## 로컬 실행

Microsoft ODBC Driver 18과 Azure CLI 로그인이 필요하다. Python 3.13 환경에서 의존성을 설치한 뒤 실행한다.

```bash
cd apps/gold-sync
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt

FABRIC_SQL_SERVER=... \
FABRIC_SQL_DATABASE=watchback_lakehouse_dev_v2 \
DATABASE_URL='postgresql://...' \
PYTHONPATH=src python -m watchback_gold_sync
```

로컬에서는 `DefaultAzureCredential`이 Azure CLI 로그인을 사용한다. Managed Identity를 사용할 때는 `AZURE_CLIENT_ID`를 함께 전달한다. 토큰과 DB 접속 문자열은 출력하지 않는다.

Docker로 Live 검증할 때는 Azure CLI가 발급한 단기 토큰을
`FABRIC_SQL_ACCESS_TOKEN` 환경변수로 전달할 수 있다. 토큰은 파일이나 명령
인자에 직접 기록하지 않으며, 운영 실행은 `DefaultAzureCredential`을 사용한다.

성공과 실패 모두 stdout에 JSON 한 건만 출력한다. Batch 하나가 실패하면 해당 Batch만 롤백하고 다른 정상 Batch는 계속 처리하지만 프로세스는 실패 코드로 종료한다.

## 테스트와 Docker

```bash
python -m pip install -r requirements-dev.txt
python -m pytest
docker build -t watchback-gold-sync apps/gold-sync
```

Container Apps Job 배포와 실행 스케줄은 이 Worker의 범위에 포함하지 않는다.
