# Watchback Fabric — Silver Layer Notebooks

설계서(`01_개요와_전체구조.md` ~ `08_운영Lifecycle_핵심원칙.md`)의 **Silver 레이어**를 구현한 Microsoft Fabric PySpark 노트북 14개입니다. 모든 산출물은 Delta Table(`Tables`)로 저장됩니다.

## 파일 목록 (04_Notebook_설계.md §4.1 그대로)

| # | 노트북 | 출력 테이블 | 비고 |
|---|--------|------------|------|
| 00 | `00_silver_common` | – | 공용 설정/유틸. 다른 모든 노트북이 첫 셀에서 `%run 00_silver_common` |
| 01 | `01_validate_ghsa` | `stg_ghsa_valid`, `reject_ghsa` | Fatal(식별자 없음)만 Reject, 나머지는 Warn 플래그만 |
| 02 | `02_normalize_ghsa` | `stg_ghsa_normalized` | 날짜/Severity/CVSS/Identifier 후보 필드 표준화 |
| 03 | `03_build_advisory_ghsa` | `silver_advisory_ghsa` | SCD2, grain = `ghsa_id` + valid period |
| 04 | `04_build_vuln_alias` | `silver_vuln_alias` | GHSA↔CVE Crosswalk, append-only |
| 05 | `05_build_affected_range` | `silver_advisory_ghsa_affected` | grain = `ghsa_id`×`package_key`×`range`, GHSA 단위 전체 교체 |
| 06 | `06_build_package` | `silver_package` | 패키지 Entity, 신규 `package_key`만 append |
| 07 | `07_build_active_cve_set` | `active_cve_set` | EPSS 추적 대상 CVE. `first_seen_in_scope`/`last_seen_in_scope`/`discovered_by_batch_id` 관리 (기존 구현 갭 보강) |
| 08 | `08_validate_epss` | `stg_epss_valid`, `reject_epss` | CSV.gz 헤더에서 `snapshot_date`/`model_version` 파싱 |
| 09 | `09_build_silver_epss` | `silver_epss` | `active_cve_set` 필터, DAILY/BACKFILL 모드 |
| 10 | `10_build_epss_distribution` | `silver_epss_distribution` | Bronze EPSS 전량 집계, `is_systemic`(3상태) 판정 |
| 11 | `11_validate_kev` | `stg_kev_valid`, `reject_kev` | 이벤트 소싱(`event_type`) 파싱, `meta_watermark` 기반 증분 읽기, 결정적 `batch_id`=파일명 |
| 12 | `12_build_silver_kev` | `silver_kev` | 스냅샷 diff 제거 — `event_type`별 분기(added/updated는 CORE_FIELDS 해시 비교, removed_confirmed는 버전 닫기 전용) |
| 13 | `13_reconcile_silver` | `meta_dq_metric` | Bronze = Silver + Reject 항등식 검증, 불일치 시 예외 발생 |

## 실행 순서 / 의존성 (05_Job_Orchestration.md 대응)

```
GHSA: validate_ghsa → normalize_ghsa → build_advisory_ghsa
                                     → build_vuln_alias
                                     → build_affected_range → build_package
                                     → build_active_cve_set

EPSS: validate_epss → build_silver_epss (DAILY)
                    → build_epss_distribution

KEV:  validate_kev(워터마크 기반, 새 이벤트 파일이 있을 때마다 또는 주기적으로 트리거) → build_silver_kev
      -- BACKFILL 시에는 target_cve_ids로 스코프를 좁혀 워터마크 없이 전체 이력을 읽음

공통: (GHSA/EPSS 모두 끝난 뒤) reconcile_silver
```

`build_silver_epss`는 `active_cve_set`을 참조하므로 **GHSA 경로가 최소 한 번은 먼저 성공**해야 합니다(최초 구축 시). 이후 일상 운영에서는 GHSA/EPSS가 서로 다른 Gold 테이블만 건드리는 것처럼, Silver 단계도 서로 독립적으로 스케줄할 수 있습니다.

## 노트북 파라미터 (모든 노트북 공통, `00_silver_common`에서 정의)

```python
run_mode = "DAILY"        # INITIAL | DAILY | EVENT | BACKFILL | REPLAY
source = "ghsa"           # ghsa | epss | kev
snapshot_date = None      # "YYYY-MM-DD", None이면 오늘(UTC)
target_cve_ids = []       # EVENT / BACKFILL 대상
target_ghsa_ids = []      # REPLAY 등 특정 GHSA만 재처리할 때
batch_id = None           # None이면 노트북이 자체 발급(단독 테스트용)
is_backfill = False
```

**중요**: 실제 Job/Pipeline에서 여러 노트북을 체이닝할 때는 **Pipeline이 `batch_id`를 한 번 발급해 모든 노트북에 동일하게 전달**해야 합니다. `reconcile_silver`가 `reject_*` 테이블을 `batch_id` 기준으로 집계하기 때문에, 각 노트북이 제각각 `batch_id`를 새로 발급하면 Reconciliation이 깨집니다.

## Bronze 경로 규칙 (가정)

```
Files/bronze/ghsa/{snapshot_date}/*        (JSON 또는 JSONL)
Files/bronze/epss/{snapshot_date}/*.csv.gz
Files/bronze/kev/*                          (날짜 하위폴더 없음 -- event_type별 누적 이벤트 로그,
                                              파일명 = {run_at}_{commit_sha[:7]}.json)
```
실제 Lakehouse의 Bronze 적재 경로가 다르면 `00_silver_common`의 `BRONZE_*_PATH` 상수만 고치면 됩니다 — 이후 모든 노트북이 자동으로 따라갑니다.

KEV는 GitHub 변경 감지 / 파일 Fetch / Hash 비교를 이미 별도 Function이 수행하므로, Fabric은 `Files/bronze/kev`를 **읽기만** 합니다 — Fabric 쪽에 KEV용 GitHub API 폴링 로직은 없습니다(애초에 만들지 않았습니다).

## 설계서 요건 반영 체크리스트

- **원본 불변 / Reject 재처리 가능**: 모든 validate 노트북이 `raw_payload`를 통째로 Reject 테이블에 보관 (§5.1)
- **NULL ≠ FALSE**: `silver_epss_distribution.is_systemic`은 전일 비교 불가 시 `NULL`, `False`(판정했지만 아님)와 구분 (03_Gold_Schema.md §3.7 원칙을 Silver부터 적용)
- **행 삭제 금지**: `active_cve_set`은 매번 MERGE(UPDATE/INSERT만) — 오늘 alias에 안 잡혀도 기존 행을 지우지 않음
- **불필요한 버전 분기 방지**: `silver_advisory_ghsa`/`silver_advisory_ghsa_affected`/`silver_kev` 모두 `record_hash`에서 `dq_flags`·`batch_id`·`ingested_at` 등 파생/실행 메타를 제외
- **Business Key 안정성**: `silver_advisory_ghsa_affected`는 `range_idx`가 아니라 `ghsa_id+package_key+vulnerable_version_range`로 키를 잡고, `range_idx`는 lineage 컬럼으로만 보관 (03_Gold_Schema.md §3.7 사전 반영)
- **EPSS Bronze 전량 보존 + BACKFILL**: `build_silver_epss`가 `run_mode=="BACKFILL"`일 때 Bronze 과거 전체를 다시 스캔
- **Systemic Change 우선 판정**: `build_epss_distribution`이 개별 CVE 판정보다 먼저 실행되는 구조(별도 Job 단계)로 배치
- **KEV 워터마크 증분 처리**: `validate_kev`가 `meta_watermark`(source=`cisa_kev`)를 기준으로 새 이벤트 파일만 읽고, 처리 후 워터마크를 전진시킴 — 누적 로그 전체를 매번 다시 읽지 않음
- **KEV 결정적 batch_id**: `validate_kev`가 이벤트 파일명(`{run_at}_{commit_sha[:7]}`)을 그대로 `batch_id`로 사용 — 같은 이벤트를 재처리해도 항상 같은 값
- **KEV `catalog_version`은 상태 판정에 안 씀**: lineage 컬럼으로만 보관하고 별도 `STALE_CATALOG_VERSION` 류 DQ 플래그는 만들지 않음(요구사항 A-6)

## 이 산출물의 범위 밖 (Out of scope)

- Gold Internal/Publish 노트북 (`gold_vuln_package_build` 등) — `03_Gold_Schema.md`/`04_Notebook_설계.md` §4.2 참고, 별도 요청 시 작성
- `meta_job_run`(노트북 단위 상태)은 테이블 정의만 `TBL`에 있고, 실제 population은 Pipeline/오케스트레이터 책임 (설계서 Part 7)
- DS팀 `priority_score` 연동은 Gold 레이어의 관심사

## 변경 이력 — KEV 이벤트 소싱 전환

기존 "KEV 배치 목록 스냅샷을 매번 통째로 diff" 방식에서, 별도 Function이 GitHub 변경 감지/Fetch/Hash 비교를 마치고 `event_type`(`kev_added`/`kev_updated`/`kev_removed_confirmed`) 단위 이벤트를 내려주는 방식으로 KEV 입력 구조가 바뀌면서 아래 파일들을 수정했습니다.

| 파일 | 무엇이 바뀌었나 |
|------|------------------|
| `00_silver_common.ipynb` | ① `BRONZE_KEV_EVENT_PATH` 상수 제거(배치/실시간 경로 구분이 없어짐, `BRONZE_KEV_PATH` 하나로 통합) ② `TBL`에 `meta_watermark` 추가 ③ `nested_or_none`/`nested_coalesce` 헬퍼를 `02_normalize_ghsa`에서 공용으로 승격(KEV의 `data.*` 중첩 필드 파싱에도 재사용) ④ `get_watermark`/`update_watermark` 헬퍼 신규 추가 |
| `02_normalize_ghsa.ipynb` | 로컬에 있던 `nested_or_none` 정의를 제거하고 공용 헬퍼를 그대로 사용하도록 수정(동작 변화 없음, 중복 제거) |
| `11_validate_kev.ipynb` | **전면 재작성**. JSON/CSV 겸용 `read_kev_source`(추측 기반 포맷 판별) 제거 — Function이 포맷을 이미 정규화하므로 JSON 고정 읽기로 단순화. `BRONZE_KEV_PATH/*`를 파일명(`_file_stem`)·`run_at`(`_run_at`)과 함께 읽고, `run_mode=="BACKFILL"`이 아니면 `meta_watermark`의 마지막 처리 지점 이후 파일만 필터링. Fatal 조건에 `event_type` 유효성 검증 추가(`kev_added`/`kev_updated`/`kev_removed_confirmed` 외의 값은 Reject). `batch_id`를 노트북 실행 단위 값 대신 **이벤트 파일명 그대로**(`_file_stem`)로 스탬프. 처리 종료 후 워터마크 전진. |
| `12_build_silver_kev.ipynb` | **전면 재작성**. "어제 전체 vs 오늘 전체" 스냅샷 diff 로직 없음(애초에 그런 로직이 아니라 CORE_FIELDS 해시 비교 방식이었지만, 이번 기회에 이벤트 기반으로 재구성). 필드 소스를 최상위 컬럼 후보 나열 방식에서 `data.*` 중첩 구조 파싱(`nested_coalesce`)으로 변경. `event_type`으로 분기: `kev_added`/`kev_updated`는 기존 CORE_FIELDS 해시 비교(changed/unchanged) 로직 그대로 재사용, `kev_removed_confirmed`는 새 셀로 분리해 **현재 열린 버전을 닫기만** 하고 새 버전을 열지 않음. `valid_from` 우선순위를 `date_added → ingested_at`에서 **`detected_at`(이벤트 발생 시각) → date_added → ingested_at**으로 변경. `catalog_version`/`source_commit_sha`를 lineage 전용 컬럼으로 추가(상태 판정에 미사용, 별도 DQ 플래그 없음). |
| `13_reconcile_silver.ipynb` | 안내 문구만 수정 — "GHSA/EPSS/KEV가 같은 batch_id를 공유해야 한다"는 문구에서 KEV를 제외(KEV는 이제 이벤트 파일명 기반 `batch_id`를 쓰고, 이 노트북의 Reconciliation 항등식 대상에도 원래 포함되지 않았음을 명시). 로직 변경 없음. |

`03_gold_circuit_breaker_check`를 포함한 Gold 노트북들은 `silver_kev`의 컬럼(`kev_listed`/`date_added`/`required_action`/`valid_from`/`valid_to`/`cve_id`)만 참조하고 이번에 그 스키마는 바뀌지 않았으므로, **Gold 쪽은 수정하지 않았습니다.**

## 실행 환경 참고

이 환경에는 PySpark/Delta/Java가 없어 Fabric 클러스터 실행 자체는 테스트하지 못했습니다. 대신 모든 노트북의 코드 셀을 이어 붙여 `compile()`로 문법 검증했고, `TBL` 딕셔너리 키 사용/정의 일치, cell 간 import 순서(특히 `StructType`/`Window` 등 로컬 import가 사용 시점보다 앞에 오는지)를 정적으로 재확인했습니다. Fabric에 올린 뒤 실제 Bronze 샘플 데이터로 한 번 dry-run 해보는 것을 권장합니다.
