## 1. 목적

이 계약은 DS 탐지 로직이 산출하고 DE가 Gold로 적재하며 Web이 재검토 후보 설명에 사용할 후보 결과와 근거 필드 형식을 정의한다.

## 2. Gold 출력 테이블

탐지 결과 Gold 출력은 3개의 테이블로 구성한다.

```
gold_rereview_batch
= 배치 정보

gold_rereview_candidate
= 특정 배치에서 선정된 재검토 후보

gold_rereview_candidate_evidence
= 후보를 뒷받침하는 근거 (후보:근거=1:N)
```

## 3. `gold_rereview_batch`

### 3.1 Grain

`batch_id` 기준 1행

### 3.2 필드

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `batch_id` | string | yes | Gold 후보 선정 실행 결과 묶음 식별자 |
| `run_id` | string | no | 오케스트레이션에서 공유하는 run_id |
| `status` | string | yes | Batch 완료 여부. Web에서는 `completed`만 읽는다 |
| `as_of` | timestamp | yes | 후보 선정에 사용한 데이터의 기준 시점 |
| `generated_at` | timestamp | yes | Gold 결과가 생성된 시각 |
| `policy_version` | string | yes | 후보 선정에 사용한 정책/루브릭 버전 |
| `schema_version` | string | yes | Gold 후보 결과 스키마 버전 |
| `candidate_count` | int | yes | Batch에 포함된 고유 `candidate_id` 수 |

## 4. `gold_rereview_candidate`

### 4.1 Grain

`batch_id + candidate_id` 기준 1행이다.

### 4.2 필드

Silver 신호를 DS 룰로 평가해 만든 재검토 후보의 식별자, 선정 여부, 우선순위, 대표 사유를 저장한다.

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `batch_id` | string | yes | 후보가 포함된 Gold Batch 식별자 |
| `candidate_id` | string | yes | 후보 결과 식별자 |
| `signal_snapshot_date` | date | yes | 평가에 사용한 Silver 신호 기준일 |
| `lookback_snapshot_date` | date | yes | D-30 비교 기준일 |
| `ghsa_id` | string | yes | GHSA 식별자 |
| `cve_id` | string | no | 대표 CVE 식별자 |
| `package_ecosystem` | string | yes | 패키지 ecosystem |
| `package_name` | string | yes | 패키지 이름 |
| `affected_range` | string | no | 취약 영향 버전 범위 |
| `priority` | string | yes | `P0`, `P1`, `P2`, `P3` 중 하나 |
| `score_total` | int | yes | 최종 점수. Web 상세 분석 또는 운영 검증에서 사용 |
| `risk_change_score` | int | yes | A축 위험 변화 점수 |
| `current_severity_score` | int | yes | B축 현재 심각도 점수 |
| `actionability_change_score` | int | yes | C축 조치 가능성 변화 점수 |
| `trigger_types` | array<string> | yes | 후보가 된 트리거 유형 목록. 예: `KEV_NEW`, `EPSS_RISE_D30`, `PATCH_NEW` |
| `primary_trigger_type` | string | yes | 대표 선정 사유 코드. |
| `reason_summary` | string | yes | 사람이 읽을 수 있는 대표 선정 사유 |
| `observed_at` | timestamp | yes | 후보의 대표 위험 변화가 관찰된 시각 |
| `selected_at` | timestamp | yes | 해당 변화가 재검토 후보로 선정된 시각 |

예시:

```json
{
  "batch_id": "gold-20260819-01",
  "candidate_id": "candidate-001",
  "signal_snapshot_date": "2026-08-19",
  "lookback_snapshot_date": "2026-07-20",
  "ghsa_id": "GHSA-abcd-1234",
  "cve_id": "CVE-2026-12345",
  "package_ecosystem": "npm",
  "package_name": "lodash",
  "affected_range": "<4.17.21",
  "priority": "P1",
  "score_total": 85,
  "risk_change_score": 40,
  "current_severity_score": 25,
  "actionability_change_score": 20,
  "trigger_types": ["EPSS_RISE_D30", "PATCH_NEW"],
  "primary_trigger_type": "EPSS_RISE_D30",
  "reason_summary": "외부 공격 가능성 지표가 30일 전보다 크게 상승하고, 새로운 패치 버전이 확인되었습니다.",
  "observed_at": "2026-08-19T00:00:00Z",
  "selected_at": "2026-08-19T01:00:00Z"
}
```

## 5. `gold_rereview_candidate_evidence`

### 5.1 Grain

`batch_id + evidence_id` 기준 1행이며, 하나의 `candidate_id`는 여러 `evidence_id`를 가질 수 있다.

### 5.2 필드

각 재검토 후보가 선정되거나 제외된 근거를 신호 단위로 나누어 이전값, 현재값, 출처와 함께 저장한다.

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `batch_id` | string | yes | 후보가 포함된 Gold Batch 식별자 |
| `candidate_id` | string | yes | 연결된 후보 식별자 |
| `evidence_id` | string | yes | 근거 식별자 |
| `rule_id` | string | yes | 근거를 만든 룰 ID. 예: `R-KEV-NEW` |
| `signal` | string | yes | 신호 종류. 예: `kev`, `epss_score`, `epss_percentile`, `cvss`, `patch` |
| `previous_value` | string | no | 이전 값. 배열/객체는 JSON string으로 표현 가능 |
| `current_value` | string | no | 현재 값. 배열/객체는 JSON string으로 표현 가능 |
| `value_type` | string | yes | `boolean`, `decimal`, `string`, `date`, `array`, `object` 중 하나 |
| `evidence_observed_at` | timestamp | yes | 해당 근거가 관찰된 시각 |
| `source` | string | yes | 근거 출처. 예: `GitHub Advisory`, `FIRST EPSS`, `CISA KEV` |
| `source_snapshot_at` | timestamp | no | 원천 데이터 기준 시각 |
| `source_snapshot_date` | date | no | 원천 데이터 기준 날짜 |
| `evidence_summary` | string | yes | 사람이 읽을 수 있는 근거 설명 |

예시:

```json
[
  {
    "batch_id": "gold-20260819-01",
    "candidate_id": "candidate-001",
    "evidence_id": "evidence-001",
    "rule_id": "R-EPSS-RISE-D30",
    "signal": "epss_score",
    "previous_value": "0.02",
    "current_value": "0.35",
    "value_type": "decimal",
    "evidence_observed_at": "2026-08-19T00:00:00Z",
    "source": "FIRST EPSS",
    "source_snapshot_at": null,
    "source_snapshot_date": "2026-08-19",
    "evidence_summary": "EPSS가 30일 전 대비 17.5배 상승했습니다. (0.02 → 0.35)"
  },
  {
    "batch_id": "gold-20260819-01",
    "candidate_id": "candidate-001",
    "evidence_id": "evidence-002",
    "rule_id": "R-GHSA-PATCH-NEW",
    "signal": "patch",
    "previous_value": "[]",
    "current_value": "[\"4.17.21\"]",
    "value_type": "array",
    "evidence_observed_at": "2026-08-19T00:00:00Z",
    "source": "GitHub Advisory",
    "source_snapshot_at": "2026-08-19T00:30:00Z",
    "source_snapshot_date": null,
    "evidence_summary": "30일 전에는 패치 버전이 없었으나 현재 patched version이 확인되었습니다."
  }
]
```

## 6. 참고용 Trigger 매핑표

- `rule_id`: Evidence row에서 어떤 정책 룰이 충족됐는지 식별하는 내부 판정 ID
- `trigger_types`: Gold candidate 단위에서 해당 후보에 걸린 Trigger들을 요약해 담는 목록
- `primary_trigger_type`: 여러 Trigger 중 후보를 대표해서 UI나 정렬/요약에 우선 표시할 Trigger 1개
- `signal`: Evidence row에서 해당 룰 판단에 사용된 원천 신호 또는 신호군

| N | Rule ID | trigger_types | signal |
| --- | --- | --- | --- |
| 1 | `R-KEV-NEW` | `KEV_NEW` | `kev` |
| 2 | `R-EPSS-RISE-D30` | `EPSS_RISE` | `epss_score` |
| 3 | `R-EPSS-TOP5-ENTRY-D30` | `EPSS_TOP5_ENTRY` | `epss_percentile` |
| 4 | `R-GHSA-SEV-CRITICAL-CVSS9` | `SEV_CRITICAL_CVSS9` | `severity_cvss` |
| 5 | `R-GHSA-SEV-CRITICAL-XOR-CVSS9` | `SEV_CRITICAL_XOR_CVSS9` | `severity_cvss` |
| 6 | `R-GHSA-SEV-CVSS8` | `SEV_CVSS8` | `severity_cvss` |
| 7 | `R-GHSA-PATCH-NEW` | `PATCH_NEW` | `patch` |
| 8 | `R-GHSA-PATCH-CHANGE` | `PATCH_CHANGE` | `patch` |
