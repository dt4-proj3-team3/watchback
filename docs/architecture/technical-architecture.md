# Watchback Technical Architecture

| 항목 | 내용 |
| --- | --- |
| 관련 문서 | [PRD](../product/prd.md) · [Product Backlog](../product/product-backlog.md) · [SP1 Backlog](../product/sp1-backlog.md) |

## 1. 범위

이 문서는 Watchback 개발에 사용하는 외부 데이터 소스, 주요 실행 구성요소와 데이터 흐름을 설명한다. 제품 요구사항, Sprint 작업, API 필드와 DB 스키마는 반복하지 않는다.

## 2. 외부 데이터 소스

| 소스 | 사용하는 데이터 |
| --- | --- |
| GitHub Dependabot API | 조직·저장소의 Alert, 패키지, 상태와 조치 결과 |
| GitHub Advisory Database | GHSA, CVE, CVSS, 영향 버전과 패치 정보 |
| FIRST EPSS | CVE별 일별 EPSS 점수와 percentile |
| CISA KEV | 실제 악용이 확인된 CVE와 등재 정보 |

NVD와 OSV는 현재 수집 범위에 포함하지 않는다.

## 3. 구성요소와 리소스

| 구성요소 | 기술·리소스 | 역할 |
| --- | --- | --- |
| 데이터 플랫폼 | Microsoft Fabric | 원본 수집, 이력 저장과 글로벌 위험 변화 분석 |
| 운영 DB | PostgreSQL / Azure Database for PostgreSQL | 웹 조회 데이터와 사용자 검토 활동 저장 |
| Backend | FastAPI | 고객 Alert 연결, 웹 API와 GitHub 조치 연동 |
| Frontend | Next.js | 재검토와 조치 화면 |
| KEV 수집기 | Azure Functions | CISA KEV 변경 확인과 단주기 수집 |
| Dependabot Sync Worker | Azure Container Apps Job | Alert 주기 수집과 상태 동기화 |
| 애플리케이션 실행 환경 | Azure Container Apps | Frontend·Backend 실행 |
| 비밀정보 관리 | Azure Key Vault·Managed Identity | 운영 자격 증명 관리 |
| 로그·모니터링 | Application Insights | 애플리케이션 로그와 상태 모니터링 |

## 4. 시스템 흐름

```text
┌────────────────────────────── 1. 외부 위험 데이터 ──────────────────────────────┐
│                                                                                │
│   [ GHSA ]                 [ FIRST EPSS ]                 [ CISA KEV ]          │
│   GitHub 보안 권고         악용 가능성 점수                실제 악용 확인 목록   │
│                                                                                │
└────────────────────────────────────────────────────────────────────────────────┘
    GHSA·EPSS ─────────────── 일일 배치 ───────────────────────────┐
    CISA KEV ──▶ [ Azure Function · 단주기 변경 확인·수집 ] ──────┴──▶
┌────────────────────────────── 2. Microsoft Fabric ─────────────────────────────┐
│                                                                                │
│       [ Bronze ]                [ Silver ]                 [ Gold ]             │
│        원본 저장       ───▶     정규화·연결·이력화    ───▶  위험 변화 분석      │
│                                                                                │
└────────────────────────────────────────────────────────────────────────────────┘
                         ▲ 검토·처리 결과 적재
                         │
                         │ 위험 분석 결과 동기화
                         ▼
┌────────────────────── 3. 조직 Alert·재검토 서비스 ─────────────────────────────┐
│                                                                                │
│ [ GitHub / Dependabot ] ─REST─▶ [ Sync Worker ] ─▶ [ PostgreSQL ]              │
│   조직·저장소별 Alert             Container Apps Job      ▲   │                 │
│          │                                               │   ▼                 │
│          └──────────── Webhook ───────────────────▶ [ Backend ] ◀──▶ [ Web ]   │
│                                                    FastAPI         Next.js     │
│                                                                                │
└────────────────────────────────────────────────────────────────────────────────┘
                         │ 비밀정보·로그·모니터링
                         ▼
┌──────────────────────────────── 4. 공통 운영 ──────────────────────────────────┐
│                                                                                │
│       [ Azure Key Vault·Managed Identity ]       [ Application Insights ]      │
│         비밀정보 관리                              로그·모니터링                │
│                                                                                │
└────────────────────────────────────────────────────────────────────────────────┘
```

사용자 요청은 PostgreSQL을 조회하며 Fabric을 직접 조회하지 않는다. Fabric과 PostgreSQL 사이의 구체적인 전달 계약은 SP1에서 확정한다.

## 5. 소유권 및 책임 경계

### 팀 책임

| 팀 | 책임 |
| --- | --- |
| DE | GHSA·EPSS·KEV 수집, 정제와 Fabric 내 이력 관리 |
| DS | 의미 있는 위험 변화와 시스템성 변동 분석 |
| Web | Dependabot Alert 수집·동기화, 고객 Alert 연결, 화면·사용자 활동·GitHub 조치 |

### 데이터 처리 경계

| 데이터·결과 | 생산 책임 | 소비 | 책임 범위 |
| --- | --- | --- | --- |
| Dependabot Alert | Web | Web | GitHub에서 Alert를 수집하고 현재 상태를 동기화한다. |
| 외부 위험 신호 | DE | DS | GHSA·EPSS·KEV를 수집·정제하고 이력을 제공한다. |
| 위험 변화 후보 | DS | Web | 위험 변화와 시스템성 변동을 분석하고 선정 근거를 제공한다. |
| 재검토 Case | Web | 사용자 | 위험 변화 후보를 조직의 Dependabot Alert와 연결해 사용자 검토 대상으로 제공한다. |
| 사용자 검토·조치 결과 | Web | DE·DS | 사용자 활동과 GitHub 처리 결과를 저장하고 사후 분석에 전달한다. |

### 데이터 원본

| 데이터 | 원본 |
| --- | --- |
| 외부 위험 이력과 글로벌 변화 | Microsoft Fabric |
| Dependabot Alert와 PR 상태 | GitHub |
| 사용자 검토 활동 | PostgreSQL |

- Fabric은 고객과 무관한 위험 변화를 제공한다.
- Web은 위험 변화를 고객 Alert와 연결해 사용자 기능을 제공한다.
- 시스템 간에는 합의된 데이터 계약만 사용한다.

## 6. 구현 원본

| 대상 | 원본 |
| --- | --- |
| API 계약 | FastAPI `/openapi.json` |
| DB 구조 | SQLAlchemy·Alembic·SchemaSpy |
| Fabric–Web 데이터 계약 | `docs/contracts/`의 계약 문서 |
| Sprint 구현 작업 | GitHub Issue |
