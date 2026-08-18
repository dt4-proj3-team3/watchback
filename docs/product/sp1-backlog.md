# Watchback SP1 Backlog

| 항목 | 내용 |
| --- | --- |
| Sprint | S1 |
| 기간 | 2026-08-18 ~ 2026-08-26 |
| 팀 구성 | DE 3명 · DS 2명 · Web 1명 |
| Sprint Goal | 실데이터에서 유의미한 위험 변화가 확인된 재검토 알림 5건을 띄운다. |
| 제품 백로그 | [Watchback 제품 백로그](product-backlog.md) |
| 팀별 작업 | [DE](sp1-de-backlog.md) · [DS](sp1-ds-backlog.md) · [Web](sp1-web-backlog.md) |

## 1. 범위와 작업 계층

- S1에는 제품 백로그의 P0·P1인 US-01~US-07을 포함한다.
- Sprint Goal 달성에 필요한 수준으로만 구현하며 일반화와 고도화는 필수 범위로 보지 않는다.
- Epic 아래에서 Story와 Task는 같은 계층으로 관리한다.
- Story는 사용자 결과, Task는 여러 Story를 지원하는 기술 작업을 나타낸다.
- Story와 Task의 실제 실행 단위는 GitHub Sub-issue로 관리한다.
- 담당자, 구현 방법과 세부 완료 조건은 GitHub Issue에서 확정한다.

## 2. Sprint 결과 확인 기준

- [ ] **Epic 1 — 위험 변화 재검토:** 유의미한 위험 변화가 확인된 실제 Alert 5건을 선별하고, 선정 근거 확인부터 검토 활동 기록까지 시연할 수 있다.
- [ ] **Epic 2 — 조직 단위 조치:** 5건을 조직·패키지 단위로 요약하고, KEV 등 자동화 조건을 충족한 Alert의 업데이트 PR 생성과 처리 결과까지 시연할 수 있다.

## 3. Epic 1 — 위험 변화 재검토

누적 Alert에서 다시 볼 항목을 선별하고, 변화 근거와 작업자의 검토 활동을 연결한다.

### 3.1 Story

| ID | 우선순위 | Story | SP1 결과 |
| --- | --- | --- | --- |
| US-01 | P0 | 재검토 대상 확인 | 실제 Alert에서 유의미한 재검토 후보 5건을 확인할 수 있다. |
| US-02 | P0 | 변화 근거 확인 | 후보별 변화 전후 값, 시점, 출처와 선정 근거를 확인할 수 있다. |
| US-03 | P0 | 검토 활동 기록 및 조치 연결 | 검토 활동을 기록하고 외부 GitHub Issue·PR과 연결할 수 있다. |
| US-04 | P0 | 시스템성 변동 요약 | 집단 변동과 개별 위험 변화를 구분하고 판단 근거를 확인할 수 있다. |

### 3.2 Technical Task

| ID | 팀 | Task | 완료 결과 |
| --- | --- | --- | --- |
| DE-01 | DE | 계층·전달 계약 | Bronze·Silver·Gold와 DE·DS·Web 간 데이터 계약이 확정된다. |
| DE-02 | DE | 수집·Bronze | 정의된 범위의 EPSS·GHSA·KEV 원본과 수집 메타데이터가 Bronze에 적재된다. |
| DE-03 | DE | Silver | 외부 위험 데이터가 정규화·연결·이력화되어 DS 입력으로 제공된다. |
| DE-04 | DE | Gold | DS 위험 변화 분석 결과가 Web이 소비할 수 있는 Gold 데이터로 제공된다. |
| DE-05 | DE | Job·E2E | 수집부터 Web 전달까지 실행 흐름과 재실행 결과가 검증된다. |
| DS-01 | DS | 분석 입출력 계약 | Silver 분석 입력과 DS 결과 출력 계약이 확정된다. |
| DS-02 | DS | 위험 신호 변화 분석 | EPSS·KEV·GHSA에서 재검토에 사용할 위험 신호가 정의된다. |
| DS-03 | DS | 시스템성 변동 구분 | 집단 변동과 개별 위험 변화를 구분할 기준이 정의된다. |
| DS-04 | DS | 재검토 후보 정책·선정 | 시스템성 변동과 복합 신호의 처리 정책을 적용해 재검토 후보·우선순위·선정 근거가 생성된다. |
| DS-05 | DS | 후보 검증 | 후보 규칙의 유효성과 한계를 검토하고 Web이 Alert와 연결할 수 있는 분석 결과를 확정한다. |
| WEB-01 | Web | Web 데이터 계약 | Gold·GitHub·Web DB·API 사이의 데이터 계약이 확정된다. |
| WEB-02 | Web | Alert·위험 후보 동기화 | Dependabot Alert와 Gold 위험 후보가 Web에 동기화된다. |
| WEB-03 | Web | 재검토 Case 생성 | 위험 후보와 조직 Alert를 연결해 재검토 Case를 생성한다. |
| WEB-04 | Web | 재검토 기능 | 사용자가 재검토 목록·근거를 확인하고 검토 활동을 기록할 수 있다. |
| WEB-06 | Web | E2E 검증 | 실제 Alert 5건이 원본부터 재검토 화면까지 연결된다. |

팀별 Task의 하위 작업은 [DE](sp1-de-backlog.md), [DS](sp1-ds-backlog.md), [Web](sp1-web-backlog.md) 문서를 기준으로 관리한다.

## 4. Epic 2 — 조직 단위 조치

재검토 결과를 기간·패키지 단위로 묶고 실제 업데이트와 처리 결과 확인까지 연결한다.

### 4.1 Story

| ID | 우선순위 | Story | SP1 결과 |
| --- | --- | --- | --- |
| US-05 | P1 | 기간별 조직 위험 변화 요약 | 기간별 후보와 주요 변화 원인, 영향 저장소·패키지 분포를 확인할 수 있다. |
| US-06 | P1 | 패키지 단위 조치 후보 확인 | 동일 패키지 업데이트로 해결 가능한 Alert와 예상 해결 범위를 확인할 수 있다. |
| US-07 | P1 | 위험 조건 기반 업데이트 | KEV 등 자동화 조건을 충족하고 패치 가능한 Alert의 업데이트 PR을 자동 생성하고 처리 결과를 확인할 수 있다. |

### 4.2 Technical Task

| ID | 팀 | Task | 완료 결과 |
| --- | --- | --- | --- |
| WEB-05 | Web | 조직 단위 조치·자동화 | 기간·패키지 단위 조치 후보를 제공하고 조건을 충족한 Alert의 업데이트 PR을 자동 생성해 Case와 연결한다. |

## 5. 팀 간 합의 사항

| 경계 | 합의할 내용 |
| --- | --- |
| DE→DS | Silver에서 제공할 위험 신호의 범위, 스키마와 기준 시점 |
| DS→Gold | 위험 변화 후보·선정 근거·시스템성 변동 결과의 형식과 저장 방식 |
| Gold→Web | Web에 제공할 최소 데이터, 전달 방식과 동기화 시점 |
| 위험 후보→Alert | Gold 결과와 Dependabot Alert를 연결할 공통 식별자와 매칭 기준 |

## 6. GitHub Issue 관리

- Epic 아래에 Story와 Technical Task를 같은 계층의 Issue로 생성한다.
- 팀별 하위 작업은 Story 또는 Technical Task의 Sub-issue로 생성한다.
- 한 Story에만 필요한 구현은 해당 Story의 Sub-issue로 연결한다.
- 여러 Story를 지원하는 기반 작업은 Technical Task로 관리한다.
- 담당자, 상태, 선행 의존성, 추정값과 완료 증거는 GitHub Project에서 관리한다.
