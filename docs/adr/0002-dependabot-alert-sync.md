# ADR-0002: Dependabot Alert 전체 조회와 원자 동기화

- 상태: Accepted
- 날짜: 2026-08-21
- 관련 이슈/PR: #89
- 대체하는 ADR:
- 대체된 ADR:

## Context

Web은 조직 저장소의 Dependabot Alert를 Gold 위험 후보와 연결해야 한다. GitHub 응답은 페이지로 나뉘며 요청 실패나 불완전한 응답을 Alert 삭제로 오인하면 운영 상태가 손상될 수 있다. 구성된 시연 저장소는 한 번의 기준 데이터로 사용하므로 서로 다른 시점의 부분 반영도 허용하지 않는다.

## Decision

- `apps/dependabot-sync`의 독립 CLI Worker가 GitHub REST API `2022-11-28`로 구성된 대상 저장소의 모든 상태와 심각도 Alert를 전체 조회한다.
- 각 저장소의 메타데이터와 모든 페이지를 메모리에서 검증한 후, PostgreSQL advisory transaction lock과 단일 트랜잭션으로 Advisory 다음 Alert 순서로 반영한다.
- Advisory는 GHSA ID, Alert는 저장소 ID와 GitHub Alert 번호로 식별한다. 새 내부 ID는 외부 자연키 기반 UUIDv5로 만들고 기존 ID는 보존한다.
- 원본 필드는 수신 `github_updated_at`이 저장값보다 최신일 때만 갱신한다. 성공적으로 관찰된 저장소와 Alert의 동기화 시각은 매 실행 갱신한다.
- 전체 조회에서 누락된 기존 Alert는 삭제하거나 상태를 추론하지 않는다. GitHub가 반환한 명시적 상태만 반영한다.
- `open`, `dismissed`, `fixed`, `auto_dismissed`와 `direct`, `transitive`, `unknown`을 GitHub 원본 값 그대로 저장한다. CVE가 없는 Advisory도 저장하되 Candidate와 매칭하지 않는다.
- 한 저장소의 API·계약·DB 오류도 전체 실행을 실패시키며 어느 저장소도 부분 반영하지 않는다. 재실행은 첫 페이지부터 시작한다.
- 실행 이력 테이블과 원본 Snapshot은 만들지 않는다. 단일 JSON 실행 결과와 외부 로그 저장소가 검증 이력을 담당한다.

## Alternatives

- 저장소별 트랜잭션은 한쪽만 최신인 상태를 만들 수 있어 선택하지 않았다.
- Webhook 또는 watermark 기반 증분 수집은 S1 운영 복잡도를 늘리므로 후속 범위로 남겼다.
- 누락 Alert 삭제는 부분 응답과 실제 삭제를 구분할 수 없어 선택하지 않았다.
- Backend 패키지 재사용은 Worker 배포를 Backend 릴리스에 결합하므로 DB 계약만 공유한다.

## Consequences

- 전체 Snapshot을 메모리에 보관하므로 Alert 규모가 커지면 스트리밍 검증 전략을 다시 검토해야 한다.
- DB 스키마와 Worker SQL 사이의 정합성은 Migration 및 PostgreSQL 통합 테스트로 관리한다.
- 동시 실행은 즉시 실패하며 스케줄러가 재실행해야 한다.
- 구조화 실행 결과는 비밀정보와 원본 payload를 포함하지 않는다.

## Verification

- 대표 Fixture로 페이지네이션, 원본 enum, nullable 필드, 중복 및 재시도 계약을 검증한다.
- PostgreSQL에서 최신 값만 갱신, 재실행 멱등성, 누락 미삭제, 전체 롤백과 동시 실행 잠금을 검증한다.
- 임시 PostgreSQL에 구성된 전체 저장소를 연속 두 번 동기화해 원천 건수와 DB 건수, 해시, 두 번째 실행의 원본 변경 0건을 확인한다.
