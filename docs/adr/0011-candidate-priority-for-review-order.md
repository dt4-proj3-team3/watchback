# ADR-0011: 대표 Candidate 우선순위를 재검토 순서로 사용

- 상태: Accepted
- 날짜: 2026-08-31
- 관련 이슈/PR:
- 대체하는 ADR: ADR-0006의 Case 우선순위 표시·조회 결정
- 대체된 ADR:

## Context

DS는 위험 변화, 현재 취약점 심각도와 조치 가능성 변화를 조합해 Candidate에 `P0`~`P3` 재검토 우선순위를 부여한다. Web의 `ReviewCase.priority`는 Advisory severity인 `critical`~`low`를 복사해 저장하고 목록의 우선순위로 사용해, 취약점 자체 심각도와 다시 볼 순서를 혼동했다.

저장소 중요도와 고객별 자동조치 정책은 별도 맥락으로 유지한다. 이번 결정은 고객별 종합 우선순위를 새로 계산하지 않고 DS가 제공한 재검토 우선순위를 일관되게 사용하는 범위다.

## Decision

- 목록과 대시보드의 재검토 우선순위는 Case의 대표 Candidate `priority`를 사용한다.
- 우선순위 필터와 정렬은 `P0` → `P1` → `P2` → `P3` 순서로 처리한다.
- 사용자 화면에서는 내부 정책 코드를 직접 노출하지 않고 `P0`~`P3`를 각각 `Critical`, `High`, `Medium`, `Low` 우선순위 라벨로 표현한다. 이 라벨의 원천은 Candidate priority이며 Advisory severity와는 별개다.
- 저장소별 우선 항목 집계는 `critical` Case 대신 대표 Candidate `P0` Case를 센다.
- Advisory severity는 취약점 자체 심각도로 별도 보존·표시한다.
- `ReviewCase.priority`는 API·DB 호환성을 위해 유지하지만 신규 표시·필터·정렬에는 사용하지 않고 deprecated로 표시한다.
- Case 생성 로직의 기존 필드 기록은 이번 변경에서 유지하며, 컬럼 제거 또는 의미 재정의는 별도 Migration으로 처리한다.

## Alternatives

- Advisory severity를 계속 재검토 우선순위로 사용하는 방식은 DS가 산출한 `P0`~`P3`와 제품의 다시 볼 순서를 무시하므로 선택하지 않았다.
- `P0`~`P3`를 `critical`~`low`로 이름만 변환하는 방식은 정책 우선순위와 보안 심각도를 다시 혼동하므로 선택하지 않았다.
- 저장소 중요도까지 합친 신규 점수는 합의된 조합 규칙이 없으므로 이번 범위에 포함하지 않았다.

## Consequences

- 같은 Critical 취약점이라도 Candidate 변화 점수에 따라 서로 다른 `P0`~`P3`로 표시될 수 있다.
- 목록 API의 `priority` 쿼리 값은 `P0`~`P3`가 되며 응답의 호환용 `priority` 필드와 의미가 다르므로 소비자는 `latest_candidate.priority`를 사용해야 한다.
- 기존 Case 데이터와 Migration은 변경되지 않는다.

## Verification

- Advisory severity와 Candidate priority가 다른 Fixture에서 표시·필터·정렬이 Candidate 기준인지 확인한다.
- 대시보드, 재검토 목록과 저장소 집계가 동일한 대표 Candidate 우선순위를 사용하는지 확인한다.
- 기존 상세, 활동과 자동조치 동작이 Case 호환 필드 변경 없이 유지되는지 확인한다.
