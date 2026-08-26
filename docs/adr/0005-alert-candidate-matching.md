# ADR-0005: 위험 후보와 Dependabot Alert 매칭

- 상태: Accepted
- 날짜: 2026-08-26
- 관련 이슈/PR: #92
- 대체하는 ADR:
- 대체된 ADR:

## Context

Gold Candidate는 GHSA를 항상 제공하고 CVE를 선택적으로 제공한다. Dependabot은 같은 취약점을 저장소와 manifest별 Alert로 제공하므로, Candidate와 Alert의 연결 기준과 이력 처리 원칙이 필요하다.

## Decision

- CVE Candidate는 정규화한 CVE와 GHSA가 모두 같은 Advisory의 Open Alert에 연결한다.
- GHSA-only Candidate는 정규화한 GHSA가 같은 Advisory의 Open Alert에 연결한다.
- 식별자는 앞뒤 공백을 제거하고 대문자로 변환한 뒤 형식을 검증한다.
- Package와 manifest는 Gold 계약에 없으므로 매칭키로 사용하지 않는다.
- 같은 취약점의 Alert가 저장소·manifest별로 여러 건이면 Alert별 연결을 모두 보존한다.
- 새 매칭은 Open Alert에만 생성하고, 이후 Alert가 종료되어도 기존 연결은 삭제하지 않는다.
- 매칭은 조직 범위에서 실행하며 Case 생성은 별도 단계에서 처리한다.

## Alternatives

- CVE만 비교하면 같은 CVE를 참조하는 다른 GHSA에 잘못 연결될 수 있어 선택하지 않았다.
- Package를 매칭키로 추가하면 Gold Publish 계약 변경이 필요하므로 선택하지 않았다.
- 종료된 Alert의 매칭을 삭제하면 과거 Case의 후보 연결을 복원하기 어려워 선택하지 않았다.

## Consequences

- 하나의 Candidate가 여러 Alert에, 하나의 Alert가 시간대가 다른 여러 Candidate에 연결될 수 있다.
- CVE는 같지만 GHSA가 다른 입력은 모호한 연결로 제외된다.
- 실제 Gold 기반 최종 Case 수와 원천부터 화면까지의 검증은 #105에서 수행한다.

## Verification

- CVE·GHSA-only·CVE/GHSA 충돌을 각각 검증한다.
- manifest 중복과 여러 Candidate 전달에서 1:N·N:1 연결을 검증한다.
- 조직 격리, Open-only 신규 연결, 재실행 멱등성과 종료 Alert 이력 유지를 검증한다.
