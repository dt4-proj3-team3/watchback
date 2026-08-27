# EPSS 시계열 변화 및 KEV 특성·후보 신호 분석

## 1. 목적

이 문서는 EPSS 시계열 변화 및 KEV 특성·후보 신호 분석 범위에서 재검토 후보 생성에 사용할 EPSS·KEV 변화 신호를 정의한다.

### 1.1 분석 범위

| 구분 | 분석 대상 | 기간·기준 |
|---|---:|---|
| EPSS 시계열 | 최신 snapshot 기준 360,396개 CVE | 2025-03-18 ~ 2026-08-17, 518개 일별 snapshot |
| EPSS 후보 임계값 비교 | D-1, D-7, D-30, D-90 기준 후보 수 | 탐지 실행일 기준 합성 baseline |
| KEV 현재 등재 | 1,662개 CVE | Silver KEV 현재 상태 |
| GHSA·EPSS·KEV 조인 검증 | 조인 가능한 KEV CVE 127건 | EPSS D-30 feature와 GHSA 최신 snapshot 기준 |

관련 Notebook은 `fabric/workspace/analysis/ds02_risk_change_analysis.ipynb`이다.

## 2. 입력과 기준 시점

### 2.1 입력 데이터

| 입력 | 주요 필드 | 용도 |
|---|---|---|
| EPSS 일별 이력 | `score_date`, `cve_id`, `epss`, `percentile` | CVE별 점수·percentile 변화 탐지 |
| KEV 현재 상태 | `cve_id`, `date_added`, `kev_listed`, `valid_from`, `valid_to` | KEV 등재 여부와 등재일 확인 |
| GHSA 조인 결과 | `cve_id`, `ghsa_id`, `severity`, `cvss`, `withdrawn_at`, `vulnerabilities` | EPSS·KEV 신호 검증용 보조 맥락 |

### 2.2 비교 기준

현재 실제 `dismissed_at` 또는 과거 사용자 판단 시점이 없으므로, DS-02 분석에서는 탐지 실행일 기준 합성 baseline을 사용한다.

```text
baseline_date = detection_date - window
current_date = detection_date
```

EPSS 후보 검증은 D-1, D-7, D-30, D-90을 비교했으며, 재검토 신호로는 D-30 기준을 채택한다.

| 기준 | 해석 | 채택 여부 |
|---|---|---|
| D-1 | 하루 단위 급변 | 너무 희소해 기본 신호로 미채택 |
| D-7 | 주간 변화 | 탐지량이 작아 보조 확인으로 사용 |
| D-30 | 월간 위험 상승 | 기본 EPSS 변화 신호로 채택 |
| D-90 | 장기 변화 | 탐지량이 과도해 단독 신호로 미채택 |

### 2.3 EPSS EDA 확인 항목

EPSS EDA Notebook은 다음 항목을 확인한다.

| 확인 항목 | 목적 |
|---|---|
| 날짜별 전체 CVE 수 | snapshot 누락, 백필, 수집 범위 변화를 확인 |
| EPSS 점수 분포 | 낮은 base score의 배율 노이즈와 고위험권 점수대를 구분 |
| EPSS percentile 분포 | Top 10%, Top 5%, Top 1% 진입 후보 규모 비교 |
| CVE별 D-1, D-7, D-30, D-90 변화량 | 관찰 기간별 후보 수와 안정성 비교 |
| `epss_delta`, `epss_ratio`, `percentile_delta` | 급상승과 고위험 진입 조건 산출 |

## 3. 채택 후보 신호

### 3.1 EPSS 고위험 진입

| 항목 | 내용 |
|---|---|
| Rule ID | `R-EPSS-TOP5-ENTRY-D30` |
| 조건 | D-30 percentile `< 0.90` 이고 현재 percentile `>= 0.95` |
| 의미 | 과거에는 EPSS 고위험권 밖이었으나 현재 Top 5% 영역에 진입한 CVE |
| 채택 근거 | 전체 EPSS 기준 D-30 탐지량은 50건, 약 0.014%로 검토 가능한 규모 |
| 지속성 확인 | D-30 Top 5% 진입 50건 중 48건은 7일 이상 고위험 상태가 유지됨 |

임계값별 후보 수는 다음과 같다.

| Rule | 조건 요약 | D-1 | D-7 | D-30 | D-90 | 채택 |
|---|---|---:|---:|---:|---:|---|
| `R-EPSS-01A` | Top 10% 진입 | 97 | 293 | 1,095 | 11,274 | 미채택 |
| `R-EPSS-01B` | Top 5% 진입 | 0 | 2 | 50 | 2,787 | D-30 채택 |
| `R-EPSS-01C` | Top 1% 진입 | 0 | 1 | 8 | 189 | 미채택 |
| `R-EPSS-01D` | 현재·과거 모두 Top 5% | 17,870 | 17,770 | 17,352 | 11,796 | 미채택 |
| `R-EPSS-01E` | Top 5% 진입 후 7일 유지 | 0 | 0 | 48 | 2,741 | 보조 확인 |

Top 10% 진입은 검토량이 크고, 현재 Top 5% 지속은 이미 과거에도 고위험이었던 CVE가 다수 포함되어 "변화" 신호로 약하다. Top 1% 진입은 너무 좁아 기본 신호로 사용하지 않는다.

### 3.2 EPSS 급상승

| 항목 | 내용 |
|---|---|
| Rule ID | `R-EPSS-RISE-D30` |
| 조건 | D-30 대비 EPSS `>= 5배` 그리고 절대 증가 `>= 0.05` |
| 의미 | 낮은 EPSS 점수의 단순 배율 노이즈를 제외하고, 절대값 기준으로도 의미 있게 상승한 CVE |
| 채택 근거 | 전체 EPSS 기준 D-30 탐지량은 64건, 약 0.0179%로 검토 가능한 규모 |

임계값별 후보 수는 다음과 같다.

| Rule | 조건 요약 | D-1 | D-7 | D-30 | D-90 | 채택 |
|---|---|---:|---:|---:|---:|---|
| `R-EPSS-02A` | 3배 상승 | 5 | 20 | 217 | 164,936 | 미채택 |
| `R-EPSS-02B` | 5배 상승 | 0 | 3 | 80 | 93,457 | 미채택 |
| `R-EPSS-02C` | 5배 상승 + 0.05 증가 | 0 | 3 | 64 | 3,625 | D-30 채택 |
| `R-EPSS-02D` | 10배 상승 + 0.10 증가 | 0 | 2 | 32 | 1,382 | 보조 강도 |
| `R-EPSS-02E` | 5배 상승 + 0.05 증가 후 유지 | 0 | 3 | 64 | 3,625 | 보조 확인 |

배율 조건만 사용하지 않는다. 예를 들어 `0.0001 -> 0.0005`는 5배 상승이지만 재검토 신호로 보기 어렵다. 따라서 배율과 절대 증가를 함께 적용한다.

### 3.3 KEV 현재 등재

| 항목 | 내용 |
|---|---|
| Rule ID | `R-KEV-CURRENT` |
| 조건 | 현재 Silver KEV에 CVE가 등재되어 있음 |
| 의미 | CISA KEV Catalog에 알려진 악용 취약점으로 등록된 CVE |
| 처리 | DS-04 정책에서 KEV 기반 Risk Change 또는 우선순위 승격 근거로 사용 |

노트북의 `silver_kev` 현재 상태 기준 전체 KEV CVE 수는 1,662건이다. GHSA·EPSS·KEV가 조인 가능한 evaluation universe에서는 KEV CVE 127건이 확인됐다.

검증 universe에서 KEV CVE는 다른 고위험 proxy와 강하게 겹쳤다.

| 지표 | 값 |
|---|---:|
| KEV CVE 수 | 127 |
| 현재 EPSS Top 5% 동반 | 118건, 92.91% |
| 현재 EPSS Top 1% 동반 | 107건, 84.25% |
| GHSA Critical 동반 | 60건, 47.24% |
| CVSS `>= 9.0` 동반 | 57건, 44.88% |
| patched version 동반 | 121건, 95.28% |

이 결과는 KEV가 EPSS 고위험 신호와 자주 겹치지만, CVSS·severity와 완전히 같은 신호가 아님을 보여준다.

### 3.4 KEV와 EPSS 동반 후보 신호

KEV EDA Notebook은 KEV 등재 CVE와 EPSS 변화를 함께 확인한다.

| 후보 신호 | 조건 | 해석 |
|---|---|---|
| `R-KEV-CURRENT_WITH_EPSS_TOP5` | KEV 등재 CVE이고 현재 EPSS percentile `>= 0.95` | KEV와 현재 EPSS 고위험이 겹친 강한 재검토 후보 |
| `R-KEV-CURRENT_WITH_EPSS_TOP1` | KEV 등재 CVE이고 현재 EPSS percentile `>= 0.99` | KEV와 최상위 EPSS percentile이 겹친 후보 |
| `R-KEV-CURRENT_WITH_EPSS_RISE_D30` | KEV 등재 CVE이고 `R-EPSS-RISE-D30`도 충족 | KEV와 월간 EPSS 급상승이 동반된 후보 |
| `R-KEV-CURRENT_WITH_EPSS_TOP5_ENTRY_D30` | KEV 등재 CVE이고 `R-EPSS-TOP5-ENTRY-D30`도 충족 | KEV와 월간 고위험권 진입이 동반된 후보 |

동반 신호는 KEV를 중복 가산하기 위한 별도 축이 아니다. 사용자가 상세 근거를 볼 때 "KEV 등재와 EPSS 변화가 같이 관찰됐다"는 설명 근거로 보존한다.

## 4. KEV 동반성과 후보 신호 평가

GHSA·EPSS·KEV 조인 universe에서 EPSS 후보 신호와 KEV의 overlap/lift는 다음과 같다.

| 후보 신호 | 후보 수 | KEV 동반 | Precision-like | KEV baseline | Lift |
|---|---:|---:|---:|---:|---:|
| `R-EPSS-RISE-D30` | 14 | 2 | 14.29% | 0.43% | 33.14 |
| `R-EPSS-TOP5-ENTRY-D30` | 12 | 1 | 8.33% | 0.43% | 19.33 |
| `R-EPSS-02D-D30` | 8 | 1 | 12.50% | 0.43% | 29.00 |

EPSS D-30 급상승은 후보 수가 작지만 KEV lift가 가장 높아, 기본 EPSS 변화 신호로 유지한다. D-30 Top 5% 진입은 KEV 동반 비율은 낮지만 현재 EPSS Top 5%와 100% 겹치므로 고위험권 진입 신호로 유지한다.

## 5. 데이터 품질 처리

분석 결과를 해석할 때 필요한 최소 품질 처리는 다음과 같다.

| 항목 | 처리 | 해석 영향 |
|---|---|---|
| EPSS 원본 행 제외 | `#model_version` 행과 `cve,epss,percentile` header 행은 제외 | 메타데이터가 점수 행으로 섞이지 않게 함 |
| 유효 CVE만 사용 | `cve_id`가 `CVE-`로 시작하는 행만 사용 | EPSS·GHSA·KEV 조인 오류 방지 |
| 비교 기준 부재 | baseline 값이 없으면 해당 EPSS 룰만 미평가 | 전체 CVE를 제외하지 않고 룰별 후보 수만 낮아짐 |
| KEV 중복 CVE | KEV 현재 상태는 CVE 기준으로 중복 제거 | KEV 등재 건수가 중복 계산되지 않게 함 |

## 6. 검증 결과 요약

| 검증 항목 | 결과 |
|---|---|
| EPSS D-30 Top 5% 진입 | 전체 EPSS 기준 50건, 0.014% |
| EPSS D-30 Top 5% 진입 후 7일 유지 | 50건 중 48건 |
| EPSS D-30 5배 + 0.05 급상승 | 전체 EPSS 기준 64건, 0.0179% |
| 조인 universe의 `R-EPSS-RISE-D30` | 14건, KEV 동반 2건, KEV lift 33.14 |
| 조인 universe의 `R-EPSS-TOP5-ENTRY-D30` | 12건, KEV 동반 1건, KEV lift 19.33 |
| Silver KEV CVE | 1,662건 |
| 조인 universe의 KEV CVE | 127건, 현재 EPSS Top 5% 동반 92.91% |

## 7. 한계와 후속 확인

- 실제 사용자 판단 시점이 없어 D-30 합성 baseline을 사용했다. 향후 `dismissed_at`, 최초 관찰일, 과거 검토일이 생기면 baseline 선택 정책을 재검토한다.
- 이번 검증은 고객 Dependabot Alert 기준이 아니라 CVE 및 조인 가능한 GHSA·EPSS·KEV universe 기준이다. Web 결합 후 실제 Alert 기준 후보 수를 재검증해야 한다.
