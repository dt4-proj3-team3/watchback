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

현재 재검토 API는 계약만 정의되어 있다. 유효한 요청도 실제 DB를 조회하거나 변경하지 않고 `501 Not Implemented`를 반환한다.

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
| 저장소 | `novalink/identity-api` | GitHub repository `1340408606` | `high`, 본인확인·이미지 처리 API |

사용자 역할과 저장소의 업무 설명은 시연 시나리오용 설명이며 현재 DB 컬럼으로 저장하지 않는다. 이 시드는 Alert·Advisory·Gold Candidate·Evidence·Case를 만들지 않는다. 해당 데이터는 각 동기화 경로에서 적재한다.
