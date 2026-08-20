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
