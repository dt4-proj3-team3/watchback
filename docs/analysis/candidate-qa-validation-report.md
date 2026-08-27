# [DS-05] Gold Re-review Candidate QA & Data Lineage 검증 보고서 (Issue #77)

> **문서 경로**: `docs/analysis/candidate-qa-validation-report.md`  
> **관련 Notebook**: `fabric/workspace/analysis/ds04_gold_rereview_candidate_qa_validation.ipynb`  
> **검증 대상**: DS-04 재검토 후보 선정 룰 엔진 및 Gold 생성 파이프라인 (OneLake `ver.1` 정책)  
> **모수 데이터**: Silver 취약점 스냅샷 64,229건  

---

## 1. 검증 개요 및 목적

본 문서는 DS-04에서 확정된 3축 재검토 후보 선정 정책(`candidate-selection-policy.md`)이 실데이터 환경에서 의도한 대로 **선정(Selection)**과 **제외(Exclusion)**를 정확히 처리하는지 검증하고, 최종 생성된 Candidate/Evidence 레코드와 원천 Silver 데이터 간의 **1:1 데이터 계보(Lineage)**를 입증한 QA 검증 결과를 기록합니다.

---

## 2. 최종 후보 생성 요약 (Summary Table)

| 우선순위 (Priority) | 후보 건수 (Candidates) | 비고 |
| :--- | :---: | :--- |
| **P0 (긴급 / KEV)** | **0건** | 실공격 악용 확인에 따른 즉시 승격 (스냅샷 기간 내 신규 등재 없음) |
| **P1 (고위험 / 60점 이상)** | **4건** | EPSS 급상승 + Critical/High 심각도 결합 건 |
| **P2 (중위험 / 35점 이상)** | **11건** | 위험 변화 + High/Moderate 심각도 결합 건 |
| **P3 (모니터링 / 15점 이상)** | **1건** | 단일 변화 신호 감지 건 |
| **총계 (Total Candidates)** | **16건** | **총 생성 Evidence: 37건 (64,229건 중 99.98% 노이즈 압축)** |

---

## 3. 세부 검증 결과

### 3.1. [실험 1] 유형별 대표 선정 사례 확인 (Selection Cases)

1. **EPSS 급상승 대표 사례 (`R-EPSS-RISE-D30`)**:
   * `CVE-2026-20896` (`code.gitea.io/gitea`): 30일 전 0.0078 ➔ 현재 0.6238 (**79.67배 급상승**, P1 등급 선정)
   * `CVE-2024-37014` (`langflow`): 30일 전 0.0092 ➔ 현재 0.5748 (**62.28배 급상승**, P2 등급 선정)
   * `CVE-2026-55255` (`langflow`): 30일 전 0.0056 ➔ 현재 0.2905 (**51.88배 급상승**, P2 등급 선정)
2. **EPSS 상위 5% 고위험군 진입 대표 사례 (`R-EPSS-TOP5-ENTRY-D30`)**:
   * `CVE-2026-20896`: 백분위 52.0% ➔ **99.1% 진입**
   * `CVE-2024-37014`: 백분위 56.5% ➔ **99.0% 진입**
   * `CVE-2023-51449` (`gradio`): 백분위 81.2% ➔ **97.9% 진입**

---

### 3.2. [실험 2] 제외 후보의 제외 근거와 원천 값 확인 (Exclusion Cases)

1. **공식 철회 (Withdrawn Gate Filter)**:
   * `withdrawn_current = TRUE`인 5건의 권고(예: `GHSA-236C-VHJ4-GFXG`, `GHSA-23V3-QFRJ-WMGH`)에 대해 점수 계산 없이 **즉시 차단(`EXCLUDED_BY_WITHDRAWN_GATE`)**됨을 확인.
2. **No Trigger 제외 (고심각도이나 변화 부재 $A=0 \land C=0$)**:
   * `CVE-2020-7684` (CVSS 9.8 Critical), `CVE-2020-14001` (CVSS 9.8 Critical) 등 심각도는 최상위이나 **과거 대비 위험 변화가 전혀 없는 5건에 대해 알림 피로도 억제를 위해 정상 제외(`EXCLUDED_NO_CHANGE_TRIGGER`)**됨을 확인.
3. **점수 미달 제외 (Score < 15)**:
   * 최소 임계 점수(15점) 미만으로 탈락한 노이즈 데이터 필터링 정상 작동 확인.

---

### 3.3. [실험 3] 원천 Silver 데이터 1:1 역추적 검증 (Data Lineage)

* **검증 방식**: `ds04_candidate_evidence`의 `previous_value`, `current_value`와 원천 `silver_ds_vulnerability_signal_snapshot`의 `epss_probability_lookback`, `epss_current`, `epss_ratio_d30`을 전수 JOIN하여 값 일치 여부 대조.
* **Assert 실행 결과**:
  ```python
  assert mismatch_count == 0, "Lineage Mismatch Error"
  # 결과: Mismatch 0건 (100% Match) - PASSED
  ```
* **결론**: 모든 Evidence 요약 문구와 수치가 원천 Silver 지표와 **오차 없이 100% 일치**함을 증명 완료.
