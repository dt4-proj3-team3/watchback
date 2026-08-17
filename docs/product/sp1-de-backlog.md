# Watchback SP1 DE Task Breakdown

| 항목 | 내용 |
| --- | --- |
| Sprint | S1 · 2026-08-18 ~ 2026-08-26 |
| Sprint Goal | 실데이터에서 유의미한 위험 변화가 확인된 재검토 알림 5건을 띄운다. |
| 기준 문서 | [Watchback SP1 Backlog](sp1-backlog.md) |

## 1. DE 팀 목표

> GHSA·EPSS·KEV 실데이터를 Bronze→Silver→Gold로 처리해, Web이 조직의 Dependabot Alert와 연결할 수 있는 위험 변화 후보와 근거를 Gold에 제공한다.

DE가 Alert 5건만 수집하는 것은 아니다. 정의된 범위의 외부 데이터를 처리하고, 최종 화면에 표시할 Alert 5건 모두와 연결 가능한 Gold 결과를 제공하는 것이 SP1 책임이다.

## 2. SP1 데이터 범위

| 소스 | 수집 범위 | 규모·갱신 기준 |
| --- | --- | --- |
| EPSS | 2025-03-21부터 일별 전체 CVE Snapshot | 일 약 30만 건, 일일 배치 실행 |
| GHSA | 수집 시작일 기준 Snapshot을 생성한 뒤 지속 수집 | 일일 배치 실행. Pagination 완전성과 이후 전체·증분 갱신 방식은 SP1에서 확정 |
| CISA KEV | 수집 시작일 기준 전체 Catalog Snapshot을 생성한 뒤 지속 수집 | Azure Function으로 10분 주기 변경 확인, 변경 시 Snapshot·Diff 저장 |

모든 소스는 실제 적재 건수, 데이터 기준 시점과 수집 완료 시각을 결과에 남긴다.

## 3. DE Task 하위 작업

상위 5개 필수 작업을 한 단계 아래의 작업 묶음으로 나눈다.

| 상위 Task | 우선순위 | 하위 작업 | 산출물 형식 | 기존 산출물·활용 |
| --- | --- | --- | --- | --- |
| DE-01 계층·전달 계약 | 필수 | 외부 원본과 수집 메타데이터를 보존할 Bronze 스키마 확정 | Bronze 스키마 문서 | 기존 수집 구조와 메달리온 설계를 시작점으로 활용한다. |
| DE-01 계층·전달 계약 | 필수 | 정규화·식별자 연결·이력화를 위한 Silver 스키마 확정 | Silver 스키마 문서 | 기존 Silver 8개 테이블 설계를 검토해 확정한다. |
| DE-01 계층·전달 계약 | 필수 | DS 분석 결과와 Web 소비 요구를 반영한 Gold 출력 계약 확정 | Gold 스키마 문서 | 기존 Gold Internal·Publish 설계를 시작점으로 활용한다. |
| DE-01 계층·전달 계약 | 필수 | Silver→DS와 Gold→Web 데이터 전달 계약 확정 | 팀 간 인터페이스 계약 문서 | 기존 데이터 소유권·책임 경계를 활용한다. |
| DE-02 수집·Bronze | 필수 | EPSS 수집 및 Bronze 적재 | 수집 코드·Bronze 데이터 | 공통 HTTP 모듈과 EPSS 수집 검증 결과를 활용한다. |
| DE-02 수집·Bronze | 필수 | GHSA 수집 및 Bronze 적재 | 수집 코드·Bronze 데이터 | GHSA API 조사와 Pagination 수집 초안을 활용한다. |
| DE-02 수집·Bronze | 필수 | KEV 수집 및 Bronze 적재 | 수집 코드·Bronze 데이터 | Azure Function 기반 KEV 수집 작업을 활용한다. |
| DE-03 Silver | 필수 | GHSA Advisory·Package·식별자 정규화 | 변환 코드·Silver 데이터 | 기존 GHSA Silver 설계와 코드를 활용한다. |
| DE-03 Silver | 필수 | EPSS 시계열 이력 구성 | 변환 코드·Silver 데이터 | 기존 EPSS 이력 데이터와 Silver 코드를 활용한다. |
| DE-03 Silver | 필수 | KEV 데이터를 CVE별 현재 상태와 변경 이력으로 정규화 | 변환 코드·Silver 데이터 | 기존 KEV Silver 설계와 변경 감지 검토 결과를 활용한다. |
| DE-03 Silver | 필수 | CVE·GHSA 식별자를 기준으로 GHSA·EPSS·KEV 데이터 연결 | 연결 코드·Silver 데이터 | No-CVE·Alias 분석과 패키지 식별자 설계를 활용한다. |
| DE-04 Gold | 필수 | DS 위험 변화 분석 결과를 Web이 소비할 수 있도록 Gold 데이터 모델과 변환 구현 | 변환 코드·Gold 데이터 | 기존 Gold 모델과 빌드 설계를 활용한다. |
| DE-05 Job·E2E | 필수 | Silver 데이터를 입력으로 하는 DS 위험 변화 분석 실행 흐름 연결 | Job 구성 | 기존 Job 실행 순서 설계를 활용한다. |
| DE-05 Job·E2E | 필수 | Gold 결과를 Web이 조회할 수 있는 데이터 전달 경로에 연결 | 연동 결과 | 기존 Publish 데이터 설계를 활용한다. |
| DE-05 Job·E2E | 필수 | 수집·Bronze·Silver·Gold Job 구성과 실행 순서 연결 | Job 구성 | 기존 Job Orchestration 설계를 활용한다. |
| DE-05 Job·E2E | 필수 | 수집부터 Web 전달까지 전체 데이터 흐름과 재실행 결과 검증 | E2E 검증 결과 | 기존 멱등성·부분 재실행 Mock 결과를 활용한다. |
| DE-05 Job·E2E | 필수 | 계층별 기준 시점·건수·식별자·중복 여부 검증 | 데이터 품질 검증 결과 | 기존 데이터 검증 항목을 활용한다. |
| DE-05 Job·E2E | 필수 | 최종 Alert 5건의 원천 데이터부터 Gold 결과까지 역추적 검증 | 데이터 계보 검증 결과 | — |
| DE-05 Job·E2E | 선택 | 대표 장애 시나리오 복구 검증 | 장애복구 검증 결과 | 기존 장애복구 Mock 결과를 활용한다. |
| DE-05 Job·E2E | 선택 | 대표 Job에 증분 처리를 적용하고 Full 처리 대비 처리시간·처리량 차이 확인 | 증분 처리·비교 결과 | 기존 Gold 증분 처리 설계를 활용한다. |
| DE-05 Job·E2E | 선택 | 실행 상태와 처리 결과 관측 | 실행 로그·운영 지표 | — |
| DE-06 CI | 선택 | 핵심 파이프라인 검증의 자동화 범위를 정하고 CI에 적용 | CI 구성·검증 결과 | — |
