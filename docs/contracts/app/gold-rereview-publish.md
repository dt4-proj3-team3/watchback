# Gold 재검토 후보 Publish 계약

## 경계

- 생산자: DE
- 소비자: Web Backend Sync
- Lakehouse: `watchback_lakehouse_dev_v2`
- Schema: `gold`
- 기준 시각: Batch의 `as_of`
- 완료 조건: Publish View에는 `status=completed`인 Batch만 존재한다.

Web은 View의 데이터를 PostgreSQL에 복제하며 실제 위험도나 후보 선정 품질을 다시 판단하지 않는다.

## `publish_rereview_batch`

Grain: `batch_id` 1행

| 필드 | 타입 | 필수 | Web DB | 의미 |
| --- | --- | --- | --- | --- |
| `batch_id` | string | yes | `gold_batches.source_batch_id` | 동기화·재처리 식별자 |
| `ds_run_id` | string | no | `gold_batches.ds_run_id` | DS 실행 추적키 |
| `status` | string | yes | 저장하지 않음 | View에는 `completed`만 허용 |
| `as_of` | timestamp | yes | `gold_batches.as_of` | 후보 선정 데이터 기준 시각 |
| `generated_at` | timestamp | yes | `gold_batches.source_generated_at` | 결과 생성 시각 |
| `policy_version` | string | yes | `gold_batches.policy_version` | 후보 선정 정책 버전 |
| `schema_version` | string | yes | `gold_batches.schema_version` | 전달 스키마 버전 |
| `candidate_count` | int | yes | `gold_batches.candidate_count` | CVE·GHSA-only 후보 합계 |

## `publish_rereview_candidate`

Grain: `batch_id + candidate_id` 1행

| 필드 | 타입 | 필수 | Web DB | 의미 |
| --- | --- | --- | --- | --- |
| `batch_id` | string | yes | `gold_batch_candidates.batch_id` | Candidate가 포함된 Batch |
| `candidate_id` | string | yes | `risk_candidates.source_candidate_id` | 후보 식별자 |
| `subject_type` | string | yes | `risk_candidates.subject_type` | `CVE` 또는 `GHSA` |
| `subject_id` | string | yes | `risk_candidates.subject_id` | 공통 Alert 연결키 |
| `ghsa_id` | string | yes | `risk_candidates.ghsa_id` | GHSA 원본 식별자 |
| `cve_id` | string | no | `risk_candidates.cve_id` | CVE가 있을 때의 연결키 |
| `priority` | string | yes | `risk_candidates.priority` | `P0`~`P3` 후보 우선순위 |
| `change_type` | string | yes | `risk_candidates.change_type` | 대표 변화 유형 |
| `reason_summary` | string | yes | `risk_candidates.reason_summary` | 목록용 선정 사유 |
| `selected_at` | timestamp | yes | `risk_candidates.selected_at` | 후보 선정 시각 |

`subject_type=CVE`이면 `subject_id=cve_id`이고, `subject_type=GHSA`이면 `cve_id=null`, `subject_id=ghsa_id`여야 한다.

## `publish_rereview_candidate_evidence`

Grain: `batch_id + evidence_id` 1행

| 필드 | 타입 | 필수 | Web DB | 의미 |
| --- | --- | --- | --- | --- |
| `batch_id` | string | yes | `candidate_evidence.batch_id` | Evidence가 포함된 Batch |
| `evidence_id` | string | yes | `candidate_evidence.source_evidence_id` | Batch 안의 근거 식별자 |
| `candidate_id` | string | yes | `candidate_evidence.candidate_id` | 연결 Candidate |
| `signal` | string | yes | `candidate_evidence.signal` | 개별 위험 신호 종류 |
| `value_type` | string | yes | `candidate_evidence.value_type` | 전후 값 자료형 |
| `previous_value` | string | no | `candidate_evidence.previous_value` | 이전 값 |
| `current_value` | string | no | `candidate_evidence.current_value` | 현재 값 |
| `observed_at` | timestamp | yes | `candidate_evidence.observed_at` | Evidence 관찰 시각 |
| `source` | string | yes | `candidate_evidence.source` | 원천 데이터 이름 |
| `evidence_summary` | string | yes | `candidate_evidence.evidence_summary` | 상세 화면용 근거 설명 |

## 재처리와 오류

- 같은 Batch·Candidate의 Candidate와 정렬된 Evidence 전체를 canonical JSON으로 만들어 SHA-256을 계산한다.
- 같은 Batch에서 해시가 같으면 변경하지 않고, 다르면 완료 결과 변경으로 간주해 해당 Batch를 거부한다.
- 새 Batch의 동일 Candidate는 전달 이력을 추가하고 가장 최근 `generated_at`의 후보 필드를 현재값으로 사용한다.
- 필수값, Grain, 관계 또는 `candidate_count`가 맞지 않으면 해당 Batch 전체를 롤백한다.
- View에 추가된 미계약 컬럼은 무시하지만 계약 컬럼 누락은 오류로 처리한다.
