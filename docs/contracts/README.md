# Watchback Contracts

DE·DS·Web 사이에서 교환되는 데이터와 책임 경계를 관리합니다.

## 파일 구조

```text
docs/contracts/
├── bronze/     # 외부 원본의 보존 형식과 수집 메타데이터
├── silver/     # 정규화·연결·이력 테이블 스키마
├── gold/       # 분석 결과와 서비스 전달 테이블 스키마
├── app/        # Fabric과 애플리케이션 사이의 전달 계약
└── README.md   # 디렉터리 안내와 작성 규칙
```

계약 파일은 해당 계층 아래에 `kebab-case.md` 형식으로 두고, 파일 하나에 계약 하나를 기록합니다. 각 파일은 생산자와 소비자, 기준 시점, 키, 필드 정의, 호환성과 검증 방법을 설명합니다.

- Bronze 계약은 원본을 해석하거나 정제한 결과가 아니라 수집한 형식과 출처를 설명합니다.
- Silver와 Gold 계약은 현재 Lakehouse 테이블의 컬럼, 타입, null 허용 여부와 키를 설명합니다.
- App 계약은 Gold 결과가 PostgreSQL·Backend 등 애플리케이션 경계로 전달되는 형식을 설명합니다.
- 실행 가능한 DDL과 변경 순서는 `fabric/workspace/migrations/`에서 관리합니다.
- 스키마를 변경하는 작업은 Migration Notebook과 관련 계약 문서를 같은 변경에서 갱신합니다.
