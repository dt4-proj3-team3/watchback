# DS-04 재검토 후보 선정 정책 및 규칙 카탈로그

## 1. 목적

Watchback GitHub Issue #74의 **DS-04 복합 신호 포함·제외와 우선순위 정책**을 정의한다.

본 정책은 EPSS, KEV, GHSA 신호를 기반으로 Silver 분석 입력에서 Gold 재검토 후보와 근거를 생성하기 위한 기준이다.

- 정책 ID: `DS-04`
- 정책 버전: `ver.1`
- 적용 대상: Silver → Gold 재검토 후보 생성

---

## 2. 평가 흐름

재검토 후보는 아래 순서로 평가한다.

```text
1. Gate 검증
withdrawn?
 └─ YES → 제외
 └─ NO
      ↓
2. Trigger 검증
A/C Trigger 존재?
 └─ NO → No Trigger
 └─ YES
      ↓
3. 점수 산출
축별 룰 평가
 ├─ 동일 축 → MAX
 └─ 축 간   → SUM
      ↓
ReReviewScore 산출
      ↓
4. 우선순위 부여
KEV 신규?
 └─ YES → P0
 └─ NO  → 점수 기준 P1~P3
      ↓
동률 시
A축 점수 높은 순 → Trigger 발생 시점 최신순
      ↓
5. Gold 근거 생성
```

### 2.1 Gate 검증

`withdrawn_current = true`인 GHSA는 즉시 제외한다.

- Withdrawn Gate는 모든 Trigger, 점수, P0 특례보다 우선한다.
- 제외된 항목은 재검토 후보로 생성하지 않는다.

### 2.2 Trigger 검증

A축 Risk Change 또는 C축 Actionability Change 중 하나 이상 충족되어야 재검토 후보가 될 수 있다.

```text
A = 0 AND C = 0 → No Trigger
```

B축 Current Severity는 점수 보정용이며, 단독으로 후보를 생성하지 않는다.

### 2.3 비교 기준값 부재

baseline 또는 previous snapshot이 없는 경우 전체 평가를 중단하지 않고 해당 룰만 미평가한다.

| 부재한 비교값 | 미평가 룰 |
|---|---|
| EPSS D-30 baseline | `R-EPSS-RISE-D30`, `R-EPSS-TOP5-ENTRY-D30` |
| 직전 KEV snapshot | `R-KEV-NEW` |
| 직전 GHSA snapshot | `R-GHSA-PATCH-NEW`, `R-GHSA-PATCH-CHANGE` |

---

## 3. 점수 산정

```text
ReReviewScore = A. Risk Change + B. Current Severity + C. Actionability Change
```

- 동일 축에서 여러 룰이 충족되면 가장 높은 점수 하나만 반영한다. 즉, 축별 `MAX`를 적용한다.
- 서로 다른 축의 점수는 합산한다. 즉, 축 간 `SUM`을 적용한다.
- 점수에 반영되지 않은 충족 룰도 Gold에는 보존한다.

---

## 4. 규칙 카탈로그

### 4.1 Gate

| Rule ID | 조건 | 처리 |
|---|---|---|
| `R-GHSA-WITHDRAWN` | `withdrawn_current = true` | 즉시 제외 |

### 4.2 A축 - Risk Change

| Rule ID | Trigger | 점수 | 판정 조건 |
|---|---|---:|---|
| `R-KEV-NEW` | KEV 신규 등재 | +50 | 직전 미등재 → 현재 CISA KEV 등재 |
| `R-EPSS-RISE-D30` | EPSS 급상승 | +40 | D-30 대비 EPSS ≥ 5배 **AND** 절대 증가 ≥ 0.05 |
| `R-EPSS-TOP5-ENTRY-D30` | EPSS 고위험 진입 | +25 | D-30 percentile < 0.90 **AND** 현재 percentile ≥ 0.95 |

### 4.3 B축 - Current Severity

| Rule ID | Trigger | 점수 | 판정 조건 |
|---|---|---:|---|
| `R-GHSA-SEV-CRITICAL-CVSS9` | Critical + CVSS 9 이상 | +25 | `severity = Critical AND CVSS ≥ 9.0` |
| `R-GHSA-SEV-CRITICAL-XOR-CVSS9` | Critical 또는 CVSS 9 이상 단일 충족 | +15 | `(Critical AND CVSS < 9.0) OR (Not Critical AND CVSS ≥ 9.0)` |
| `R-GHSA-SEV-CVSS8` | CVSS 8점대 | +5 | `Not Critical AND 8.0 ≤ CVSS < 9.0` |

### 4.4 C축 - Actionability Change

| Rule ID | Trigger | 점수 | 판정 조건 |
|---|---|---:|---|
| `R-GHSA-PATCH-NEW` | 패치 신규 등장 | +20 | 직전 patched version 없음 → 현재 존재 |
| `R-GHSA-PATCH-CHANGE` | 패치 버전 변경 | +15 | 직전 snapshot 대비 patched version 상향·변경 |

---

## 5. 우선순위

### 5.1 P0 특례

`R-KEV-NEW`가 충족되면 점수와 무관하게 P0으로 분류한다.

단, `withdrawn_current = true`인 경우 Withdrawn Gate가 우선하므로 제외한다.

### 5.2 점수 기반 우선순위

P0 특례가 아닌 후보는 `ReReviewScore` 기준으로 분류한다.

| Priority | 기준 |
|---|---:|
| P1 | `ReReviewScore >= 60` |
| P2 | `ReReviewScore >= 35` |
| P3 | `ReReviewScore >= 15` |

`ReReviewScore < 15`인 경우 후보로 생성하지 않는다.

### 5.3 동률 처리

동률은 다음 순서로 정렬한다.

1. A축 Risk Change 점수가 높은 순
2. Trigger 발생 시점이 최신인 순

---

## 6. Gold 근거 생성 규칙

- 동일 축 MAX 정책으로 최종 점수에 반영되지 않은 Trigger도 Gold 테이블에 보존한다.
- 테이블 상세 스키마는 별도 Gold 출력 계약에서 정의한다.

| Gold 테이블 | 저장 내용 |
|---|---|
| `gold_rereview_candidate` | 특정 배치에서 선정된 재검토 후보의 최종 점수, 우선순위, 정책 버전 등 후보 선정 결과 |
| `gold_rereview_candidate_evidence` | 후보를 뒷받침하는 Trigger별 근거. 충족된 모든 Trigger의 근거를 1:N으로 저장 |


---

## 7. 후속 검토 사항

Dependabot Alert 결합 후 다음 항목을 최종 재검토한다.

- 후보 식별·병합 기준 및 동률 처리 정책
- Alert 상태 변화의 Trigger 포함 여부

