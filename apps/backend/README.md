# Watchback Backend

FastAPI와 PostgreSQL로 Watchback의 재검토 API 및 운영 데이터를 관리한다.

## 개발 환경 준비

아래 명령은 `apps/backend`에서 실행한다. 별도의 `uv` 설치는 필요하지 않다.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

운영 의존성만 필요하면 `requirements.txt`를 설치한다.

## API 문서 확인

```bash
python -m uvicorn watchback_backend.main:app --reload --app-dir src
```

- Swagger UI: <http://localhost:8000/docs>
- ReDoc: <http://localhost:8000/redoc>
- OpenAPI JSON: <http://localhost:8000/openapi.json>

재검토 API는 `DATABASE_URL`의 PostgreSQL 운영 DB를 조회하고 활동을 저장한다. 애플리케이션 import와 OpenAPI 문서 조회에는 DB 연결이 필요하지 않지만 실제 API 요청에는 연결 가능한 DB가 필요하다.

세 API 모두 S1 임시 요청 컨텍스트로 다음 UUID 헤더를 요구한다.

- `X-Organization-ID`: 요청 조직
- `X-User-ID`: 조직에 소속된 작업자

별도 인증은 아직 수행하지 않으며, 헤더의 사용자가 요청 조직에 소속됐는지만 DB에서 확인한다.

```bash
curl 'http://localhost:8000/api/v1/review-cases?status=open' \
  -H 'X-Organization-ID: ORGANIZATION_UUID' \
  -H 'X-User-ID: USER_UUID'
```

목록은 기본적으로 열린 Case를 우선순위 내림차순으로 반환한다. 상세는 Alert에 연결된 전체 Candidate·Batch·Evidence·활동 이력을 반환한다. 활동 API에서 `risk_accepted`를 기록하면 열린 Case가 해결 상태로 바뀌며, 그 외 활동은 Case 상태를 변경하지 않는다.

## 테스트

```bash
python -m pytest
```

스키마 통합 테스트는 Testcontainers로 PostgreSQL 16 컨테이너를 실행하므로 로컬 Docker가 실행 중이어야 한다.

## Database Migration

Alembic은 `DATABASE_URL` 환경변수를 우선 사용한다.

```bash
export DATABASE_URL='postgresql+psycopg://USER:PASSWORD@HOST:PORT/DATABASE'
python -m alembic upgrade head
```

최초 Migration을 되돌려야 할 때만 다음 명령을 사용한다.

```bash
python -m alembic downgrade base
```

## 시연 기준 데이터

Migration 적용 후 아래 명령으로 시연용 조직·사용자·저장소를 구성한다. `DATABASE_URL`이 없으면 실행하지 않는다.

```bash
export DATABASE_URL='postgresql+psycopg://USER:PASSWORD@HOST:PORT/DATABASE'
PYTHONPATH=src python -m watchback_backend.db.demo_seed
```

기준 시점은 `2026-08-20T07:30:00Z`이며, 실행 결과로 생성·갱신·변경 없음 건수와 내부 UUID를 출력한다. 같은 DB에 다시 실행해도 행을 중복 생성하지 않는다.

재실행 시 조직 표시명, 사용자 정보, 저장소 표시명·중요도는 기준값으로 복구한다. 저장소 `full_name`, 기본 브랜치와 GitHub 시각은 최초 생성 후 동기화 작업이 관리하므로 덮어쓰지 않는다. 외부 식별자가 서로 다른 기존 행을 가리키면 전체 작업을 롤백한다.

일반 저장소 동기화는 새 행의 `display_name`을 `full_name`으로 초기화한다. 이후 동기화에서는 별도로 지정한 화면 표시명을 보존한다.

| 구분 | 표시 이름 | 원본 식별자 | 중요도·역할 |
| --- | --- | --- | --- |
| 조직 | 노바링크 | GitHub organization `314105294` (`dt4-proj3-team3`) | 시연 회사 |
| 사용자 | 김서연 | `seoyeon.kim@novalink.example` | 재검토 담당자 |
| 사용자 | 박준호 | `junho.park@novalink.example` | 조치 담당자 |
| 저장소 | `novalink/customer-fe` | GitHub repository `1329314801` | `critical`, 고객 금융 포털 |
| 저장소 | `novalink/ai-platform-api` | GitHub repository `1340408606` | `high`, AI 모델 서빙·LLM 게이트웨이 API |

사용자 역할과 저장소의 업무 설명은 시연 시나리오용 설명이며 현재 DB 컬럼으로 저장하지 않는다. 이 시드는 Alert·Advisory·Gold Candidate·Evidence·Case를 만들지 않는다. 해당 데이터는 각 동기화 경로에서 적재한다.
