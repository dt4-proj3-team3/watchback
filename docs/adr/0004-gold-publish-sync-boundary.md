# ADR-0004: Gold Publish 동기화 경계

- 상태: Accepted
- 날짜: 2026-08-26
- 관련 이슈/PR: #126
- 대체하는 ADR: ADR-0001의 CVE-only Candidate 연결 결정
- 대체된 ADR:

## Context

Gold Publish 계약은 CVE 후보와 CVE가 없는 GHSA-only 후보를 함께 제공하며, Evidence 식별자는 Batch 안에서만 유일하다. 기존 Web 모델은 Candidate의 CVE를 필수로 두고 Evidence를 전역 식별자로 저장해 이 계약을 보존할 수 없다.

## Decision

- Candidate는 GHSA를 항상 저장하고 CVE를 선택적으로 저장한다.
- `subject_type`과 `subject_id`로 CVE·GHSA 연결 기준을 명시한다.
- Candidate의 `P0`~`P3`는 Case 우선순위 및 Advisory 심각도와 변환 없이 분리해 보존한다.
- Evidence는 Batch와 Candidate 전달 관계에 귀속시켜 `(batch_id, evidence_id)` Grain을 유지한다.
- 완료 Batch는 불변으로 취급하고 같은 Batch의 payload가 달라지면 갱신하지 않는다.
- 동기화는 Batch별 원자성을 보장한다.

## Alternatives

- GHSA-only 후보 제외는 생산자가 제공한 후보를 손실하므로 선택하지 않았다.
- `P0`~`P3`를 `critical`~`low`로 변환하면 정책 우선순위와 보안 심각도를 혼동하므로 선택하지 않았다.
- Evidence를 Candidate에만 연결하면 Batch별 재전달 내용을 복원할 수 없어 선택하지 않았다.

## Consequences

- Alert 매칭은 #92에서 CVE가 있으면 CVE, 없으면 GHSA를 사용해야 한다.
- Candidate API에는 별도 우선순위 타입과 subject 필드가 노출된다.
- 계약 전환 Migration은 기존 Gold 동기화 영역이 비어 있을 때만 적용한다.

## Verification

- CVE 및 GHSA-only 후보를 각각 적재한다.
- 같은 evidence ID를 서로 다른 Batch에 저장한다.
- 동일 Batch 재실행과 변경된 완료 Batch 거부를 확인한다.
- 한 Batch 실패가 다른 정상 Batch를 롤백하지 않는지 확인한다.
