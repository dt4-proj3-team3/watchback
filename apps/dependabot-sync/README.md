# Dependabot Alert Sync Worker

GitHub 조직의 두 시연 저장소에서 모든 Dependabot Alert를 조회해 PostgreSQL 운영 DB에 반영하는 독립 CLI Worker다. Backend 패키지를 런타임에 import하지 않는다.

## 로컬 실행

Python 3.13 환경에서 의존성을 설치한다.

```bash
cd apps/dependabot-sync
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

DB에는 Backend의 최신 Alembic Migration과 시연 기준 데이터가 먼저 적용돼 있어야 한다. 두 환경변수는 필수이며 기본값은 없다.

```bash
GITHUB_TOKEN=... DATABASE_URL=postgresql://... \
  PYTHONPATH=src python -m watchback_dependabot_sync
```

토큰은 fine-grained PAT 또는 GitHub App installation token을 사용할 수 있으며 두 저장소의 `Dependabot alerts: read` 권한이 필요하다. Worker는 GitHub REST API `2022-11-28`을 사용한다.

성공과 실패 모두 stdout에 JSON 한 건만 출력한다. 토큰, Authorization 헤더, 원본 payload는 출력하지 않는다. 누락된 기존 Alert는 삭제하거나 상태를 추론하지 않으며, 두 저장소의 전체 응답을 검증한 뒤 하나의 DB 트랜잭션으로 반영한다.

## 테스트

```bash
python -m pip install -r requirements-dev.txt
python -m pytest
```

PostgreSQL 통합 테스트에는 실행 중인 Docker가 필요하다. 실제 GitHub API 검증은 전체 Snapshot을 저장하지 않고 실행 결과의 건수·해시만 보존한다.

## Docker

```bash
docker build -t watchback-dependabot-sync apps/dependabot-sync
docker run --rm \
  -e GITHUB_TOKEN \
  -e DATABASE_URL \
  watchback-dependabot-sync
```

이미지는 Python 3.13 기반이며 non-root 사용자로 실행한다. Azure Container Apps Job 및 Key Vault 배포는 별도 작업 범위다.
