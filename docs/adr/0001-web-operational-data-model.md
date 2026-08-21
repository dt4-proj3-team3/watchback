# ADR-0001: Web 운영 데이터 모델 경계

- 상태: Accepted
- 날짜: 2026-08-19
- 관련 이슈/PR: #85
- 대체하는 ADR:
- 대체된 ADR:

## Context

Web은 Fabric Gold의 위험 변화 Candidate를 조직의 Dependabot Alert와 연결하고, 사용자의 재검토와 조치 이력을 PostgreSQL에 저장한다. 스키마의 현재 상태는 SQLAlchemy로 관리하므로, 이 ADR은 코드만으로 알 수 없는 식별자와 수명 주기 규칙만 기록한다.

## Decision

- Gold Batch, Candidate, Evidence는 고객과 독립적인 전역 데이터로 저장한다.
- 동일 Candidate의 재전달과 정정은 같은 외부 `candidate_id`를 사용하고, 새로운 위험 변화는 새 ID를 사용한다.
- Candidate와 Dependabot Alert Advisory는 CVE ID로 매칭하고 매칭 결과를 별도로 보존한다. CVE가 없는 Advisory는 Candidate와 매칭하지 않는다.
- Batch별 `payload_hash`는 Candidate와 연결된 Evidence 집합을 정규화한 전체 payload를 대상으로 계산하여 Evidence 정정도 재전달 변경으로 감지한다.
- Dependabot Alert는 `(repository_id, github_alert_number)`로 식별하며, 수신한 `github_updated_at`이 저장된 값보다 최신일 때만 현재 상태를 갱신한다. 동일하거나 오래된 응답은 기존 상태를 덮어쓰지 않는다.
- Alert 상태가 `open`이면 종료 시각을 모두 비우고, `dismissed`이면 `dismissed_at`, `fixed`이면 `fixed_at`, `auto_dismissed`이면 `auto_dismissed_at`을 저장한다.
- Dependabot 동기화 응답에서 Alert가 누락됐다는 사실만으로 기존 Alert를 삭제하지 않는다. 부분 응답·페이지네이션 실패·일시적인 수집 실패를 삭제로 해석하지 않고, GitHub가 제공한 명시적인 상태를 기준으로 현재 상태를 갱신한다.
- Dependabot Alert당 Review Case는 하나만 유지한다. 해결된 Case에 새 Candidate가 연결되면 기존 Case를 재오픈하고 활동 이력을 추가한다.
- 조직 소유 행은 `organization_id`를 직접 가지며 복합 외래 키로 조직 간 참조를 차단한다.
- 저장소 `full_name`은 GitHub 연동 식별자로 보존하고, 화면에는 별도 `display_name`을 사용한다. 새 저장소의 최초 동기화에서는 `display_name`을 `full_name`으로 채우고 이후 동기화는 기존 표시명을 덮어쓰지 않는다.
- 검토 활동은 append-only 이력으로 취급한다. Issue·PR처럼 외부 상태가 변하는 대상은 별도 테이블에 저장한다.

## Alternatives

- Candidate를 Alert 하위에 복제하는 방식은 Gold 재전달 이력과 조직별 복제를 구분하기 어려워 선택하지 않았다.
- Candidate마다 Case를 새로 만드는 방식은 하나의 Alert에 대한 검토 흐름을 분산시켜 선택하지 않았다.
- 애플리케이션 조회만으로 조직을 격리하는 방식은 오작동 시 DB가 잘못된 참조를 허용하므로 선택하지 않았다.

## Consequences

- SQLAlchemy 모델이 Web 운영 DB 스키마의 단일 현재 상태가 된다.
- Alembic은 변경 이력을, SchemaSpy는 적용된 DB의 구조 문서를 생성한다.
- `0001` Migration을 Web 운영 DB의 최초 기준점으로 사용하며 레거시 DB 이전 경로는 제공하지 않는다.
- Case 재오픈과 append-only 활동은 DB 제약만으로 완결되지 않으므로 서비스 트랜잭션에서 구현한다.

## Verification

- 빈 PostgreSQL DB에 `0001` Migration을 적용하고 이후 변경은 이 기준점 위에 누적한다.
- 다른 조직의 Alert·Case·Activity 참조가 복합 FK로 거부되는지 확인한다.
- Batch·Candidate·Match 재처리와 Alert당 Case 생성이 유일키로 제한되는지 확인한다.
