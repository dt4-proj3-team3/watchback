# ADR-0006: 재검토 Case 생성과 대표 후보

- 상태: Accepted
- 날짜: 2026-08-26
- 관련 이슈/PR: #93
- 대체하는 ADR:
- 대체된 ADR:

## Context

한 Alert에는 시간대가 다른 Candidate가 여러 건 연결될 수 있고 같은 Candidate가 여러 Gold Batch로 재전달될 수 있다. 목록의 현재 요약과 상세의 누적 변화 이력을 함께 제공하면서 Case 중복과 불필요한 재오픈을 막을 기준이 필요하다.

## Decision

- Dependabot Alert당 Review Case는 한 건만 유지한다.
- 새 Case와 재오픈은 현재 Open Alert에만 적용한다. Alert 종료만으로 기존 Case 상태를 자동 변경하지 않는다.
- Case의 대표 Candidate는 `selected_at`, ID 내림차순으로 정하고 대표 Batch는 `source_generated_at`, `as_of`, ID 내림차순으로 정한다.
- Case는 대표 Candidate와 Batch를 직접 참조한다. 대표 사유는 Candidate의 `reason_summary`, Case 우선순위는 Advisory의 `severity`를 사용한다.
- Candidate의 `P0`~`P3`와 Repository 중요도는 Case 우선순위로 변환하지 않고 별도로 보존한다.
- 열린 Case는 더 최신인 대표 Candidate·Batch로 요약을 갱신한다. 해결된 Case는 대표 Candidate가 달라질 때만 재오픈하며 동일 Candidate의 Batch 재전달만으로 재오픈하지 않는다.
- Case 생성과 재오픈 시각은 Web이 처리한 UTC 시각을 사용한다.
- 목록과 상세 상단은 Case의 대표 Candidate를 표시한다. 상세는 연결된 모든 Candidate를 시간순으로 제공하고, 동일 Candidate가 여러 Batch로 재전달한 동일 Evidence는 표현 단계에서 한 번만 보여준다.
- Evidence 중복은 `signal`, `observed_at`, 이전 값, 현재 값, `source`가 모두 같을 때로 제한한다. 날짜나 값이 다른 같은 신호는 별도 변화로 유지한다.
- 시스템성 변동 억제는 S1 Gold 계약에 포함되지 않으므로 Case 생성에서 판단하지 않는다.

## Alternatives

- 매 조회마다 최신 Candidate를 계산하면 Case를 만들거나 재오픈한 기준 Batch를 고정할 수 없어 선택하지 않았다.
- Candidate마다 Case를 만들면 Alert의 검토 이력이 분산되므로 선택하지 않았다.
- 같은 신호를 모두 중복 제거하면 서로 다른 날짜의 유효한 위험 변화를 잃으므로 선택하지 않았다.

## Consequences

- Case 생성 전에 Match와 Candidate의 Gold Batch 전달 이력이 모두 존재해야 한다.
- 실제 변화 이력은 Candidate와 Evidence에 누적되고 Case는 현재 대표값만 보존한다.
- 해결된 Case에 새 Candidate가 연결되면 기존 Case ID와 사용자 활동을 유지한 채 재오픈된다.

## Verification

- 실제 Alert Snapshot과 화면형 Gold Fixture의 Match 24건이 Alert별 Case 14건으로 생성되는지 확인한다.
- 동일 입력 재실행, 열린 Case 갱신, 해결 Case 재오픈과 동일 Candidate 재전달을 각각 검증한다.
- 상세 응답에서 재전달 Evidence 중복만 제거되고 서로 다른 시점의 Candidate가 유지되는지 확인한다.
