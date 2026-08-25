# EPSS Bronze Ingestion


---

## 1. 목적

EPSS Bronze Ingestion은 FIRST EPSS Daily CSV.gz 파일을 다운로드하고, 최소 파일 검증을 거친 뒤 가공하지 않은 Raw와 수집 Metadata를 Bronze 영역에 함께 보존하기 위한 수집 기준을 정의한다.

EPSS는 하루 전체 CVE 점수가 한 번에 갱신되는 데이터이므로, 매일 전체 CSV.gz를 Snapshot 단위로 보존한다.

Bronze에서는 CVE를 미리 거르지 않는다. 현재 GHSA와 연결되지 않은 CVE도 이후 새롭게 연결될 수 있기 때문에, 과거 EPSS를 다시 사용할 수 있도록 전체 원본을 남긴다.

이 문서는 `fabric/workspace/transformation/01_ingest_epss.ipynb`의 수집 흐름, Bronze 저장 정책, Metadata 필드, Silver 연계 기준을 설명한다.


---

## 2. 적용 범위

이 문서는 EPSS 데이터를 Bronze 계층에 수집하는 작업에 적용한다.

- 수집 대상: FIRST EPSS Daily CSV.gz
- 수집 주기: 1일 1회
- 저장 위치: Bronze 영역의 EPSS Raw 및 Metadata
- 실행 방식:
  - Daily Snapshot 수집
  - 필요 시 과거 일자 Backfill 수집

이 문서는 Bronze 수집과 저장 기준만 다룬다. GHSA와의 CVE 연결, 시계열 구성, 시스템성 변동 분석은 Silver 또는 후속 분석 계층에서 수행한다.


---

## 3. 수집 정책

EPSS 수집은 다음 흐름을 따른다.

```text
FIRST Daily CSV.gz 다운로드
-> 최소 파일 검증
-> Raw + _meta.json Bronze 저장
```

EPSS는 일별 전체 CVE 점수가 하나의 CSV.gz 파일로 제공되는 Snapshot 성격의 데이터이다. 따라서 증분 변경분만 저장하지 않고, 수집 대상 일자의 전체 파일을 Bronze에 보존한다.

Daily 수집에서는 최신 EPSS CSV.gz를 다운로드하고, Backfill 수집에서는 지정한 날짜 범위의 과거 CSV.gz를 일자별로 다운로드한다.

Bronze 단계에서는 CVE를 GHSA 연결 여부로 필터링하지 않는다. 현재 GHSA와 연결되지 않은 CVE도 이후 신규 GHSA, alias, package 식별자 연결 과정에서 다시 필요할 수 있으므로, EPSS 원본 전체를 재처리 가능한 형태로 보존한다.


---

## 4. Bronze 저장 정책

Bronze에는 가공하지 않은 EPSS CSV.gz Raw와 수집 Metadata를 함께 보존한다.

- Raw 파일은 다운로드한 CSV.gz bytes를 그대로 저장한다.
- Metadata 파일은 Raw 파일과 1:1로 대응되는 `_meta.json` 파일로 저장한다.
- Bronze 단계에서는 CVE 필터링, GHSA 연결, 점수 변환, 중복 제거를 수행하지 않는다.
- 실제 시계열 구성과 GHSA 연결 기준 필터링은 Silver에서 수행한다.

Bronze 저장 파일은 다음 형태를 사용한다.

```text
epss_{snapshot_date}_{fetched_at UTC}.csv.gz
epss_{snapshot_date}_{fetched_at UTC}_meta.json
```

`epss_{snapshot_date}_{fetched_at UTC}.csv.gz`는 FIRST에서 받은 원본 압축 파일이다. `epss_{snapshot_date}_{fetched_at UTC}_meta.json`은 해당 Raw 파일의 수집 시각, 기준일, 건수, checksum 등 검증에 필요한 정보를 저장한다.


---

## 5. 파일 검증 기준

EPSS Bronze 저장 전 최소 파일 검증을 수행한다.

검증 기준은 다음과 같다.

- gzip 압축을 정상적으로 해제할 수 있어야 한다.
- CSV로 정상 parsing할 수 있어야 한다.
- 필수 컬럼 `cve`, `epss`, `percentile`이 존재해야 한다.
- record 수가 0건이면 실패로 본다.
- 파일 상단 metadata에서 `score_date`를 추출할 수 있어야 한다.
- 과거 일자 Backfill 수집에서는 요청한 일자와 실제 `score_date`의 날짜가 일치해야 한다.

검증에 실패한 파일은 Bronze에 저장하지 않는다. 실패 원인은 호출부에서 오류로 기록하고, 해당 일자는 재실행 대상으로 남긴다.


---

## 6. Daily Snapshot과 Backfill

Daily 수집은 최신 EPSS Snapshot을 하루 1회 수집하는 실행 경로이다.

Daily 수집에서는 현재 EPSS CSV.gz를 다운로드하고, 검증 결과에서 추출한 `snapshot_date`를 기준으로 Raw 파일명과 Metadata를 생성한다.

Backfill 수집은 지정한 시작일과 종료일 사이의 과거 EPSS Snapshot을 일자별로 수집하는 실행 경로이다.

Backfill 수집에서는 각 일자별 CSV.gz를 다운로드한 뒤, 요청 날짜와 파일 내부 `score_date`에서 추출한 `snapshot_date`가 일치하는지 확인한다. 일부 일자에서 실패하더라도 성공 일자와 실패 일자를 분리해 기록한다.


---

## 7. Silver 연계 기준

Silver에서는 Bronze에 저장된 EPSS 전체 원본 중 GHSA와 연결된 CVE를 기준으로 `silver_epss` 시계열을 만든다.

EPSS Bronze는 GHSA 연결 여부와 무관하게 전체 CVE 점수 분포를 보존한다. 이렇게 보존한 전체 EPSS 분포는 개별 CVE 위험도 변화뿐 아니라, 특정 일자에 전체 점수 분포가 함께 움직이는 시스템성 변동 분석에도 별도로 활용할 수 있다.

Silver 연계 기준은 다음과 같다.

- Bronze Raw에서 `cve`, `epss`, `percentile`, `snapshot_date`를 추출한다.
- GHSA와 연결된 CVE를 기준으로 `silver_epss` 시계열을 구성한다.
- GHSA와 아직 연결되지 않은 CVE는 Bronze 원본에 남겨 향후 재처리 가능성을 보장한다.
- 전체 EPSS 분포는 시스템성 변동 분석을 위해 별도 활용할 수 있다.


---

## 8. Metadata 필드

### `epss_{snapshot_date}_{fetched_at UTC}.csv.gz`

| 컬럼명 | 타입 | 담고 있는 내용 |
| --- | --- | --- |
| `cve` | string | CVE 식별번호. 예: `CVE-1999-0001` |
| `epss` | float | 향후 30일 내 실제 악용될 확률 점수. 0부터 1 사이 값이며 1에 가까울수록 악용 가능성이 높음 |
| `percentile` | float | 전체 CVE 중 해당 EPSS 점수가 위치하는 백분위. 예: `0.9211`이면 전체의 92.11% 이상 CVE보다 위험도가 높음 |

### `epss_{snapshot_date}_{fetched_at UTC}_meta.json`

| 필드 | 타입 | 내용 |
| --- | --- | --- |
| `source` | string | `"epss"` |
| `source_url` | string | 원본 다운로드 URL |
| `batch_id` | string | 배치 식별자. `epss_{fetched_at}` 형식 |
| `fetched_at` | datetime | 수집 시각. ISO 8601, UTC 기준 |
| `snapshot_date` | date | EPSS 점수 기준일 |
| `file_name` | string | 대응하는 CSV.gz 파일명 |
| `format` | string | `"csv.gz"` |
| `record_count` | integer | 레코드 수 |
| `checksum` | string | Raw CSV.gz의 sha256 checksum |
| `schema_version` | string | `"bronze-v1"` |
