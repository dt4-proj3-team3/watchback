# Watchback Fabric — Gold Layer Notebooks

`03_Gold_Schema.md`(Entity-Natural-Key + Internal/Publish 2계층)와 `04_Notebook_설계.md` §4.2를 구현한 노트북 8개입니다. Silver와 마찬가지로 전부 Delta Table로 저장됩니다.

## 파일 목록

| # | 노트북 | 출력 | 비고 |
|---|--------|------|------|
| 00 | `00_gold_common` | – | `%run 00_silver_common`으로 Silver 공용 유틸을 상속하고, Gold 테이블 이름/서킷 브레이커 임계값/as-of join 헬퍼 추가 |
| 01 | `01_gold_vuln_package_build` | `gold_vuln_package` | GHSA×package×range, 오늘 변경된 GHSA만 "부모 키 단위 전체 교체" |
| 02 | `02_gold_vuln_daily_build` | `gold_vuln_daily` | CVE×date, EPSS delta/KEV as-of/systemic 플래그. INITIAL/DAILY/BACKFILL/EVENT |
| 03 | `03_gold_circuit_breaker_check` | `meta_circuit_breaker_run` | 5개 조건 게이트, `proceed_to_publish`를 Pipeline에 반환 |
| 04 | `04_publish_vulnerability_package_build` | `publish_vulnerability_package` | 관계정보(취약점×패키지), 바뀐 것만 MERGE |
| 05 | `05_publish_risk_current_build` | `publish_risk_current` | CVE 순수 위험정보 1행, 안 바뀐 CVE는 재기록 안 함 |
| 06 | `06_publish_epss_trend_build` | `publish_epss_trend_30d` | 슬라이딩 윈도우(오늘 INSERT + 31일 전 DELETE) |
| 07 | `07_publish_risk_events_build` | `publish_risk_events` | `EPSS_SPIKE`/`KEV_NEW`, append-only |

## Job 배선 (05_Job_Orchestration.md §6.6~6.8 그대로)

```
JOB_GOLD_GHSA_SYNC (JOB_GHSA_DAILY 완료 후, EPSS 안 기다림)
  gold_vuln_package_build → publish_vulnerability_package_build

JOB_GOLD_EPSS_SYNC (JOB_EPSS_DAILY 완료 후, GHSA 안 기다림)
  gold_vuln_daily_build(DAILY)
    → gold_circuit_breaker_check           -- proceed_to_publish == false면 아래 3개 스킵
    → publish_risk_current_build → publish_epss_trend_build → publish_risk_events_build

JOB_GOLD_EVENT (KEV 실시간, target_cve_ids=[해당 CVE])
  gold_vuln_daily_build(EVENT)
    ├── publish_risk_current_build (해당 CVE만)
    └── publish_risk_events_build (해당 CVE만)
  -- publish_epss_trend_build, publish_vulnerability_package_build는 호출 안 함
     (두 노트북 모두 EVENT 모드로 부르면 RuntimeError를 던지도록 방어 코드가 있음)

JOB_CVE_BACKFILL (신규 active CVE, target_cve_ids=[신규 CVE들])
  gold_vuln_daily_build(BACKFILL) → publish_risk_events_build(BACKFILL, is_backfilled=true)
    → publish_risk_current_build(BACKFILL) → publish_epss_trend_build(BACKFILL)
```

`gold_circuit_breaker_check`는 **DAILY 경로에만** 있다 — BACKFILL/EVENT는 이미 스코프가 좁아 별도 게이트 없이 바로 publish로 간다(원 설계서에도 이 두 경로는 서킷 브레이커 표에 포함되지 않음).

## 파라미터 계약

Silver와 동일한 계약(`run_mode`, `snapshot_date`, `target_cve_ids`, `target_ghsa_ids`, `batch_id`, `is_backfill`)을 그대로 쓴다. 추가로:

- `gold_vuln_package_build`는 **GHSA daily 배치와 같은 `batch_id`**를 받아야 "오늘 변경된 GHSA"를 올바르게 좁힐 수 있다 (또는 `target_ghsa_ids`를 직접 넘겨도 됨 — REPLAY 등).
- `publish_vulnerability_package_build`는 **`gold_vuln_package_build`와 같은 `batch_id`**를 받아야 "바뀐 것만" 필터가 맞는다.

## 설계서 요건 반영 체크리스트

- **Business Key 안정성**: `gold_vuln_package`의 키는 `range_idx`가 아니라 `ghsa_id+package_key+normalized_vulnerable_version_range+first_patched_version`을 해시한 `vuln_package_key` (§3.7)
- **Grain 순수성**: `publish_risk_current`는 CVSS/심각도/패치버전을 절대 포함하지 않음 — CVE가 여러 GHSA·패키지에 걸칠 때 대표값을 정할 수 없기 때문 (§3.8, §5.7). 필요하면 Web이 `publish_vulnerability_package`를 따로 조회
- **3상태 유지**: `is_systemic_day`는 `gold_vuln_daily_build`의 `systemic_join` 헬퍼가 LEFT JOIN으로 자연스럽게 NULL을 만들어내며 별도 처리 없이 3상태 원칙을 지킴 (§3.7)
- **행 삭제 금지 / Unknown Member 불필요**: EPSS 매칭 실패 CVE는 `has_epss=false, epss_score=NULL`로 정상 행 생성 (자연키라 FK 무결성 문제 자체가 없음, 시나리오⑧)
- **증분 갱신**: GHSA/EPSS가 서로 다른 Gold 테이블만 건드리므로 두 Job이 서로 기다리지 않음 (§3.10); `publish_epss_trend_30d`는 슬라이딩 윈도우로 매일 6만 행만 갱신
- **안 바뀐 CVE 재기록 방지**: `publish_risk_current_build`는 `record_hash` 비교를 MERGE의 `whenMatchedUpdate(condition=...)`에 직접 넣어 단일 MERGE로 처리
- **서킷 브레이커**: Source Coverage / Duplicate Rate / Join Match Rate(90%) / Reconciliation(1:1) / Schema Drift 5개 전부 통과해야 Publish, 실패 시 직전 정상본 유지 (§3.11)
- **이벤트는 타깃 CVE만**: `gold_vuln_daily_build(EVENT)`, `publish_risk_current_build(EVENT)`, `publish_risk_events_build(EVENT)` 모두 `target_cve_ids`로 스코프 제한 (Targeted Incremental Processing, §6.4)

## 이 산출물에서 임의로 정한 값 (설계서에 명시 안 됨 — 운영 중 조정 필요)

- **`EPSS_SPIKE_ABS_DELTA_THRESHOLD = 0.10`**: `publish_risk_events_build`에서 EPSS 급등 판정 임계값. 설계서에는 "EPSS_SPIKE"라는 신호 이름만 있고 정확한 수치가 없어 절대값 delta 0.10을 잠정값으로 둠.
- **`coverage_score`**: `gold_vuln_daily`에서 "파생 컬럼"이라고만 되어 있고 계산식이 없어, `has_epss`를 그대로 1.0/0.0으로 매핑하는 가장 단순한 정의를 사용함.
- **Reconciliation 게이트 위치**: `gold_circuit_breaker_check`의 4번 조건(1:1 항등식)은 `run_mode=="DAILY"`일 때만 검사하고, BACKFILL/EVENT에서는 "해당 없음"으로 통과 처리 — 두 모드는 애초에 서킷 브레이커 경로를 안 타므로 실질적 영향은 없음.

## 범위 밖

- `publish_*` → Postgres 실제 적재(Web Sync Worker)는 Fabric 밖의 별도 컴포넌트이므로 포함하지 않음 (§3.12 정책만 README에 요약)
- DS팀 `priority_score`를 채우는 파이프라인 자체는 범위 밖 — `gold.ext_priority_score` 테이블이 이미 존재한다고 가정하고 LEFT JOIN만 함
