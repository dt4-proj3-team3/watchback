# Repository Layout

이 문서는 Watchback 저장소의 디렉터리별 책임과 코드 배치 기준을 정의한다.

## 디렉터리 구조

```text
apps/
├── frontend/             # Next.js 사용자 화면
├── backend/              # FastAPI·PostgreSQL Backend
├── dependabot-sync/      # Dependabot Alert 동기화 Job
└── kev-ingestor/         # CISA KEV 수집 Azure Function

data/
└── demo/                 # 버전 관리되는 데모용 데이터와 API Fixture

fabric/
└── workspace/            # API로 배포할 Fabric 항목의 로컬 원본
    ├── ingestion/        # 외부 위험 데이터 수집 Fabric 항목
    ├── transformation/   # Bronze·Silver·Gold 변환 Fabric 항목
    ├── analysis/         # 위험 변화 분석과 후보 선정 Fabric 항목
    ├── migrations/       # Lakehouse 스키마 변경 Notebook
    ├── validation/       # 데이터 품질·E2E 검증 Fabric 항목
    └── orchestration/    # Data Pipeline과 실행 순서

infra/
├── azure/                # Azure 인프라 정의
└── fabric/               # Fabric 배포·환경 설정

docs/                     # 프로젝트 문서
└── contracts/            # Bronze·Silver·Gold·App 데이터 계약
skills/                   # 재사용 가능한 에이전트 스킬
tools/                    # 제품 실행 경로에 포함되지 않는 보조 도구
```

## 배치 원칙

- 독립적으로 실행하거나 배포하는 구성요소는 `apps/`에 둔다.
- Python 애플리케이션의 import 가능한 코드는 해당 애플리케이션 내부 `src/`에 둔다.
- 애플리케이션 단위 테스트는 해당 애플리케이션 내부에 둔다.
- `fabric/workspace/`를 API로 배포할 Fabric 항목의 로컬 원본 경로로 사용한다.
- Fabric 항목은 담당 팀이나 데이터 소스보다 작업 성격을 기준으로 분류한다.
- Notebook과 Data Pipeline의 생성·배포·실행은 [Fabric API 개발 워크플로](fabric-api-workflow.md)를 따른다.
- 같은 Notebook을 Jupyter 형식과 Fabric Git Source 형식으로 중복 관리하지 않는다.
- Lakehouse 스키마 변경은 `fabric/workspace/migrations/`의 순서가 있는 Migration Notebook으로 관리한다.
- 현재 데이터 스키마와 소비자 계약은 `docs/contracts/`의 해당 계층 문서에 기록하고 Migration과 함께 변경한다.
- 공유 패키지는 둘 이상의 애플리케이션에서 실제로 재사용할 코드가 생긴 뒤 분리한다.
- 새 최상위 디렉터리를 추가하거나 기존 경로의 책임을 바꿀 때는 이 문서를 같은 변경에서 갱신한다.
