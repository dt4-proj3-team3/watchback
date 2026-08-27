# Silver to DS Analysis Input Contract

| 항목 | 내용 |
| --- | --- |
| 계약 ID | `silver-ds-analysis-input` |
| 버전 | `v0.1-draft` |
| 상태 | Draft |
| 생산자 | DE |
| 소비자 | DS |
| 관련 작업 | DS-01 분석 입출력 계약, DS-04 재검토 후보 선정 |
| 기준 루브릭 | 재검토 우선순위 산정 루브릭 `ver.1` |

## 1. 목적

이 문서는 재검토 후보 탐지에 사용할 Silver 분석 입력 View의 필드, 키, 기준 시점, 품질 검증 기준을 정의한다.


## 2. 입력 데이터셋

### 2.1 `silver_ds_vulnerability_signal_snapshot`

DS 루브릭 계산용 분석 입력 뷰

| 항목 | 내용 |
| --- | --- |
| Grain | `signal_snapshot_date` 기준 `ghsa_id` + `package_ecosystem` + `package_name` + `affected_range` 1행 |
| 기준 시점 | 일별 Silver 생성 완료 시점 |
| 주요 용도 | 재검토 우선순위 루브릭 점수 계산 |
| 필수 여부 | 필수 |

## 3. 기본 식별 및 평가 기준 필드

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `run_id` | string | yes |  |

### 3.1 키 및 대상 식별자

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `ghsa_id` | string | yes | GHSA 식별자. Dependabot Alert 매칭과 근거 표시용 |
| `cve_id` | string | no | 대표 CVE 식별자. EPSS와 KEV 조인에 사용하며 CVE가 없는 GHSA에서는 null |
| `package_ecosystem` | string | yes | 패키지 ecosystem. 예: `npm`, `maven`, `pip` |
| `package_name` | string | yes | 패키지 이름 |
| `affected_range` | string | no | 취약 영향 버전 범위 |

### 3.2 평가 기준

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `signal_snapshot_date` | date | yes | DS가 현재값으로 평가할 기준 날짜 |
| `epss_lookback_days` | int | yes | EPSS 변화 비교 기간. 루브릭 ver.1에서는 `30` |
| `epss_lookback_snapshot_date` | date | yes | EPSS 비교에 사용하는 정확한 D-30 기준 날짜. `signal_snapshot_date - epss_lookback_days`와 일치해야 함 |

## 4. Silver 입력 필드

### 현재 상태 필드:

| 필드 | 타입 | 필수 | 설명 | 검증 조건 | 참조 API |
| --- | --- | --- | --- | --- | --- |
| `withdrawn_current` | boolean | yes | 현재 GHSA withdrawn 여부 | null이면 실패. 값은 `true`, `false` 중 하나여야 한다. | GHSA |
| `withdrawn_at` | timestamp | no | withdrawn 처리 시각 | `withdrawn_current = true`이면 가능한 경우 값이 있어야 한다. `withdrawn_current = false`이면 null이어야 한다. | GHSA |
| `severity_current` | string | yes | 현재 GHSA severity | null 또는 빈 문자열이면 실패. 값은 `Critical`, `High`, `Moderate`, `Low` 중 하나여야 한다. | GHSA |
| `cvss_score_current` | double | no | 현재 CVSS base score | null 가능. null이 아니면 0 이상 10 이하이어야 한다. 대표값은 CVSS v3.1 우선, 없으면 v4.0 fallback으로 산정한다. | GHSA |
| `cvss_version_current`  | string | no | `cvss_score_current`가 참조한 CVSS 버전 | `cvss_score_current`가 null이 아니면 값이 있어야 한다. 값은 `3.1`, `4.0` 중 하나여야 한다. | GHSA |
| `cvss_vector_current` | string | no | 현재 CVSS vector | null 가능. `cvss_score_current`가 null이 아니면 가능한 경우 값이 있어야 한다. `cvss_version_current`와 같은 버전의 vector여야 한다. | GHSA |
| `epss_current` | double | no | 현재 EPSS probability | `cve_id`가 null이면 null 가능. null이 아니면 0 이상 1 이하이어야 한다. | GHSA or EPSS |
| `epss_percentile_current` | double | no | 현재 EPSS percentile. | `cve_id`가 null이면 null 가능. null이 아니면 0 이상 1 이하이어야 한다. | GHSA or EPSS |
| `kev_listed_current` | boolean | no | 현재 CISA KEV 등재 여부 | `cve_id`가 null이면 null 가능. null이 아니면 값은 `true`, `false` 중 하나여야 한다. | KEV |
| `kev_date_added` | date | no | CISA KEV 등재일 | `kev_listed_current = true`이면 가능한 경우 값이 있어야 한다. 값이 있으면 `signal_snapshot_date`보다 미래일 수 없다. | KEV |
| `patched_versions_current` | array<string> | no | 현재 patched/fixed version 목록 | null 가능. 값이 있으면 빈 문자열을 포함할 수 없고, 중복 제거 후 제공한다. | GHSA |
| `has_patch_current` | boolean | yes | 현재 패치 버전 존재 여부 | null이면 실패. 값은 `true`, `false` 중 하나여야 한다. `patched_versions_current`가 비어 있지 않으면 `true`여야 한다. | GHSA |

### EPSS D-30 비교 상태 필드: Silver 파생

| 필드 | 타입 | 필수 | 설명 | 검증 조건 |
| --- | --- | --- | --- | --- |
| `has_epss_lookback_baseline` | boolean | yes | 정확한 D-30 EPSS baseline 존재 여부 | null이면 실패. 정확한 D-30 기준 EPSS 기록이 있으면 true, 없으면 false여야 한다. |
| `epss_probability_lookback` | double | no | `epss_lookback_snapshot_date` 기준 EPSS probability | `cve_id`가 null이거나 `has_epss_lookback_baseline = false`이면 null 가능. null이 아니면 0 이상 1 이하이어야 한다. |
| `epss_percentile_lookback` | double | no | `epss_lookback_snapshot_date` 기준 EPSS percentile | `cve_id`가 null이거나 `has_epss_lookback_baseline = false`이면 null 가능. null이 아니면 0 이상 1 이하이어야 한다. |
| `epss_lookback_missing_reason` | string | no | D-30 baseline 부재 사유 | `has_epss_lookback_baseline = false`이면 가능한 경우 값이 있어야 한다. 예: `NEW_CVE`, `EPSS_NOT_AVAILABLE`, `SOURCE_GAP` |

### 직전 스냅샷 비교 상태 필드: Silver 파생

| 컬럼 | 타입 | 필수 | 설명 | 검증 조건 |
| --- | --- | --- | --- | --- |
| `kev_previous_snapshot_at` | timestamp | no | 비교에 사용한 직전 KEV 스냅샷 시각 | `kev_listed_previous`가 null이 아니면 값이 있어야 한다. 현재 KEV 스냅샷 시각보다 과거여야 한다. |
| `kev_listed_previous` | boolean | no | 직전 KEV 스냅샷 기준 CISA KEV 등재 여부 | `cve_id`가 null이면 null 가능. `cve_id`가 있으면  `true`, `false` 중 하나여야 한다. |
| `patched_versions_previous` | array<string> | no | 직전 GHSA 스냅샷 기준 patched/fixed version 목록 | null 가능. 값이 있으면 빈 문자열을 포함할 수 없고, 중복 제거 후 제공한다. |
| `has_patch_previous` | boolean | no | 직전 GHSA 스냅샷 기준 패치 버전 존재 여부 | 직전 GHSA 스냅샷이 없으면 null 가능. 값이 있으면 `true`, `false` 중 하나여야 한다. `patched_versions_previous`가 비어 있지 않으면 `true`여야 한다. |
| `ghsa_previous_snapshot_at` | timestamp | no | 비교에 사용한 직전 GHSA 스냅샷 시각 | `has_patch_previous` 또는 `patched_versions_previous` 산정에 사용한 기준 시각이다. 현재 GHSA 스냅샷 시각보다 과거여야 한다. |

### 수집·계보 메타데이터

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `ghsa_snapshot_at` | timestamp | Y | GHSA 데이터 기준 시각 |
| `epss_snapshot_date` | date | Y | EPSS 점수 기준 날짜 |
| `kev_snapshot_at` | timestamp | Y | KEV 데이터 기준 시각 |
| `silver_built_at` | timestamp | Y | Silver View 생성 시각 |
| `source_quality_flags` | array<string> | N | 누락, alias 충돌, 중복 등 품질 플래그 |

### 예시:

```json
{
  "signal_snapshot_date": "2026-08-20",
  "epss_lookback_days": 30,
  "epss_lookback_snapshot_date": "2026-07-21",

  "ghsa_id": "GHSA-abcd-1234",
  "cve_id": "CVE-2026-12345",
  "package_ecosystem": "npm",
  "package_name": "lodash",
  "affected_range": "<4.17.21",

  "withdrawn_current": false,
  "withdrawn_at": null,

  "severity_current": "Critical",
  "cvss_score_current": 9.1,
  "cvss_version_current": "3.1",
  "cvss_vector_current": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N",

  "epss_current": 0.35,
  "epss_percentile_current": 0.972,

  "kev_listed_current": true,
  "kev_date_added": "2026-08-20",

  "patched_versions_current": [
    "4.17.21"
  ],
  "has_patch_current": true,

  "has_epss_lookback_baseline": true,
  "epss_probability_lookback": 0.02,
  "epss_percentile_lookback": 0.731,
  "epss_lookback_missing_reason": null,

  "kev_previous_snapshot_at": "2026-08-19T00:40:00Z",
  "kev_listed_previous": false,

  "patched_versions_previous": [],
  "has_patch_previous": false,
  "ghsa_previous_snapshot_at": "2026-08-19T00:30:00Z",

  "epss_delta_d30": 0.33,
  "epss_ratio_d30": 17.5,
  "epss_percentile_delta_d30": 0.241,

  "kev_new_in_window": true,
  "patch_new_in_window": true,
  "patch_changed_in_window": true,

  "ghsa_snapshot_at": "2026-08-20T00:30:00Z",
  "epss_snapshot_date": "2026-08-20",
  "kev_snapshot_at": "2026-08-20T00:40:00Z",
  "silver_built_at": "2026-08-20T01:30:00Z",

  "source_quality_flags": []
}
```

### 변화 계산 보조 필드: Silver 파생

| 필드 | 타입 | 필수 | 설명 | 검증 조건 |
| --- | --- | --- | --- | --- |
| `epss_delta_d30` | double | no | `epss_current - epss_probability_lookback` | null 가능. `epss_current`와 `epss_probability_lookback`이 모두 있으면 두 값의 차이와 일치해야 한다. 둘 중 하나라도 null이면 null이어야 한다. |
| `epss_ratio_d30` | double | no | `epss_current / epss_probability_lookback` | null 가능. `epss_current`와 `epss_probability_lookback`이 모두 있고 `epss_probability_lookback > 0`이면 두 값의 비율과 일치해야 한다. `epss_probability_lookback`이 0 또는 null이거나 `epss_current`가 null이면 null이어야 한다. |
| `epss_percentile_delta_d30` | double | no | `epss_percentile_current - epss_percentile_lookback` | null 가능. `epss_percentile_current`와 `epss_percentile_lookback`이 모두 있으면 두 값의 차이와 일치해야 한다. 둘 중 하나라도 null이면 null이어야 한다. |
| `kev_new_in_window` | boolean | no | 직전 KEV 스냅샷에서 미등재였고 현재 등재된 경우 `true`  | `kev_listed_previous`와 `kev_listed_current`가 모두 있으면 null일 수 없다. `kev_listed_previous = false`이고 `kev_listed_current = true`일 때만 true여야 하며, 그 외에는 false여야 한다. 비교 가능한 직전 KEV 상태가 없으면 null 가능. |
| `patch_new_in_window` | boolean | no | 직전 GHSA 스냅샷에서 패치가 없었고 현재 패치가 있는 경우 `true` | `has_patch_previous`와 `has_patch_current`가 모두 있으면 null일 수 없다. `has_patch_previous = false`이고 `has_patch_current = true`일 때만 true여야 하며, 그 외에는 false여야 한다. `has_patch_previous = null`이면 `null`이어야 한다. |
| `patch_changed_in_window` | boolean | no | 직전 GHSA 스냅샷 대비 patched version 목록이 달라진 경우 `true`  | `patched_versions_previous`와 `patched_versions_current`를 정렬·중복 제거한 뒤 값이 다르면 `true`, 같으면 `false`여야 한다. 비교 가능한 직전 GHSA 스냅샷이 없으면 `null` 가능. |

### 예시:

```
epss_delta_d30
= 0.35 - 0.02
= 0.33

epss_ratio_d30
= 0.35 / 0.02
= 17.5

epss_percentile_delta_d30
= 0.972 - 0.731
= 0.241

kev_new_in_window
= kev_listed_previous(false)
  → kev_listed_current(true)
= true

patch_new_in_window
= has_patch_previous(false)
  → has_patch_current(true)
= true

patch_changed_in_window
= patched_versions_previous([])
  ≠ patched_versions_current(["4.17.21"])
= true
```

## 5. Silver에 두지 않는 것

```json
최종 점수
우선순위 P0~P3
후보 식별자 candidate_id
근거 식별자 evidence_id
선정 사유 reason_summary
트리거 유형 trigger_type
고객별 Dependabot Alert 상태
저장소 중요도
사용자 검토 이력
EPSS 대량 변동 맥락
EPSS 모델 버전
Web 표시용 문구
DS/Gold 출력 전용 필드
DS 탐지 로직 내부 중간 계산값
```

## 6. SP1 제외 범위

- EPSS 대량 변동 맥락은 SP1 후보 입력·출력 계약에서 제외한다.
- EPSS 모델 버전 필드는 SP1 분석 입력 View 필수 요구에서 제외한다.
