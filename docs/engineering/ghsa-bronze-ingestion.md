# GHSA Bronze Ingestion


---

## 1. 목적

GHSA Bronze Ingestion은 GitHub Advisory API에서 GHSA Advisory 데이터를 수집하고, 가공하지 않은 원본 Raw와 수집 Metadata를 Bronze 영역에 함께 보존하기 위한 수집 기준을 정의한다.

GHSA는 신규 Advisory가 계속 추가될 뿐 아니라 기존 Advisory도 수정될 수 있다. 따라서 최초 실행에서는 전체 Snapshot을 확보해 기준점을 만들고, 이후 실행에서는 마지막 정상 수집 시점 이후 변경된 범위만 증분 수집한다.

이 문서는 `fabric/workspace/transformation/02_ingest_ghsa.ipynb`의 수집 흐름, Bronze 저장 정책, Watermark 갱신 기준, Silver 연계 기준을 설명한다.


---

## 2. 적용 범위

이 문서는 GHSA 데이터를 Bronze 계층에 수집하는 작업에 적용한다.

- 수집 대상: GitHub Advisory API의 GHSA Advisory
- 수집 주기: 1일 1회
- 저장 위치: Bronze 영역의 GHSA Raw 및 Metadata
- 실행 방식:
  - 최초 1회 Full Snapshot 수집
  - 이후 Watermark 기반 Daily Incremental 수집

이 문서는 Bronze 수집과 저장 기준만 다룬다. Advisory 정규화, 중복 제거, 이력 관리, Version 관리는 Silver 계층에서 수행한다.


---

## 3. 수집 정책

GHSA 수집은 다음 흐름을 따른다.

```text
GitHub API Pagination
-> 전체 응답 검증
-> JSONL + _meta.json Bronze 저장
-> 저장 검증 성공 후 Watermark 갱신
```

GHSA는 신규 Advisory뿐 아니라 기존 Advisory도 계속 수정되기 때문에, 최초 전체 Snapshot을 확보한 뒤 이후에는 변경된 범위만 증분 수집한다.

최초 실행에서는 GitHub Advisory API의 Pagination을 끝까지 따라 전체 기준점을 만든다. 이후 실행에서는 마지막 정상 수집 시점인 Watermark와 현재 Batch 종료 시점 사이의 `modified` 범위를 조회한다.

Pagination, 응답 검증, Bronze 저장, 저장 검증 중 하나라도 실패하면 Watermark를 갱신하지 않는다. 이렇게 하면 다음 실행에서 같은 Watermark부터 다시 조회할 수 있어 빠진 구간이 생기지 않는다.


---

## 4. Bronze 저장 정책

Bronze에는 가공하지 않은 Raw와 수집 Metadata를 함께 보존한다.

- Raw 파일은 GitHub API 응답 record를 JSONL 형식으로 저장한다.
- Metadata 파일은 Raw 파일과 1:1로 대응되는 `_meta.json` 파일로 저장한다.
- Bronze 단계에서는 Advisory 내용을 정제하거나 병합하지 않는다.
- Bronze 단계에서는 중복 제거와 Version 판단을 수행하지 않는다.
- 실제 정제, 중복 제거, 이력 관리는 Silver에서 수행한다.

Bronze 저장 파일은 다음 형태를 사용한다.

```text
ghsa_{timestamp}.jsonl
ghsa_{timestamp}_meta.json
_watermark.json
```

`ghsa_{timestamp}.jsonl`은 수집된 Advisory Raw record를 한 줄에 하나씩 저장한다. `ghsa_{timestamp}_meta.json`은 해당 Raw 파일의 수집 시각, 건수, checksum, page 수 등 검증에 필요한 정보를 저장한다. `_watermark.json`은 마지막으로 정상 수집이 보장된 종료 경계를 저장한다.


---

## 5. 최초 Full Snapshot

최초 실행에서는 `modified` 범위를 제한하지 않고 GitHub Advisory API의 Pagination을 끝까지 따라 전체 GHSA Advisory Snapshot을 수집한다.

Full Snapshot의 목적은 이후 증분 수집을 시작할 기준점을 만드는 것이다.

처리 순서는 다음과 같다.

```text
1. GitHub Advisory API 호출
2. Link header의 next page를 따라 Pagination 완료
3. 전체 응답이 list 형태인지 확인
4. ghsa_id 필수값과 중복 여부 검증
5. JSONL Raw와 Metadata 생성
6. Bronze 저장
7. Source record count와 Bronze 저장 결과 검증
8. 검증 성공 후 Watermark 저장
```

Full Snapshot이 실패하면 Watermark를 저장하지 않는다. 이 경우 다음 실행에서도 Full Snapshot 또는 별도 복구 절차를 통해 기준점을 다시 만들어야 한다.


---

## 6. 증분 수집과 Watermark

Daily Incremental 수집은 마지막 정상 수집 시점인 Watermark를 기준으로 한다.

증분 수집 범위는 다음과 같이 잡는다.

```text
modified = previous_watermark..current_batch_end
```

- `previous_watermark`: `_watermark.json`의 `last_successful_watermark`
- `current_batch_end`: 현재 batch가 시작될 때 확정한 종료 경계
- 조회 대상: 해당 범위 안에서 생성 또는 수정된 GHSA Advisory

Watermark는 수집이 시작될 때 갱신하지 않는다. Pagination 완료, 응답 검증, Bronze 저장, 저장 검증이 모두 성공한 뒤에만 `current_batch_end`로 갱신한다.

이 기준을 지키면 실행 중 실패가 발생해도 다음 실행에서 이전 Watermark부터 다시 조회할 수 있다. 경계 구간의 중복 가능성은 허용하고, 누락 방지를 우선한다.

증분 수집 결과가 0건인 경우에도 해당 Watermark 구간을 정상 확인한 것이므로 Watermark를 갱신할 수 있다.


---

## 7. Pagination 처리

GitHub Advisory API는 Pagination을 사용할 수 있으므로 모든 페이지를 끝까지 수집해야 한다.

기본 정책은 다음과 같다.

- `per_page=100`을 사용해 페이지당 수집 건수를 최대화한다.
- 응답 Header의 `Link` 값을 확인한다.
- `rel="next"` 링크가 있으면 다음 페이지를 계속 조회한다.
- 더 이상 `next` 링크가 없을 때 Pagination을 완료한다.
- 중간 페이지 호출이 실패하면 전체 batch를 실패로 본다.
- Pagination 실패 시 Bronze 저장과 Watermark 갱신을 수행하지 않는다.

Pagination 완전성은 GHSA Bronze 수집에서 중요한 검증 대상이다. 일부 페이지만 저장되면 이후 Silver 계층에서 전체 기준점이나 증분 변경 범위를 신뢰하기 어렵기 때문이다.


---

## 8. 실패 시 처리 기준

GHSA 수집은 누락 방지를 우선한다. 따라서 실패한 batch는 부분 성공으로 간주하지 않는다.

다음 상황에서는 Watermark를 갱신하지 않는다.

- GitHub API 호출 실패
- Pagination 중간 실패
- 응답이 list 형태가 아닌 경우
- 필수값 검증 실패
- Bronze Raw 저장 실패
- Metadata 저장 실패
- Bronze 저장 후 record count 또는 checksum 검증 실패

Watermark가 갱신되지 않으면 다음 실행은 마지막으로 성공이 보장된 Watermark부터 다시 수집한다. 이로 인해 같은 Advisory가 다시 Bronze에 저장될 수 있지만, 누락보다 중복을 허용하는 정책을 선택한다.

중복 제거와 최신 Version 판단은 Silver 계층에서 `ghsa_id`와 `record_hash`를 기준으로 처리한다.


---

## 9. Silver 연계 기준

Silver에서는 Bronze Raw를 읽어 `ghsa_id` 기준으로 Advisory를 정규화한다.

GHSA Advisory는 기존 record가 수정될 수 있으므로, 같은 `ghsa_id`가 다시 수집되더라도 무조건 중복으로 버리지 않는다. Silver에서는 기존 `record_hash`와 새로 수집된 record의 hash를 비교한다.

- `ghsa_id`가 처음 등장한 경우: 신규 Advisory로 적재
- `ghsa_id`가 이미 존재하고 `record_hash`가 같은 경우: 동일 내용으로 보고 새 Version을 만들지 않음
- `ghsa_id`가 이미 존재하고 `record_hash`가 다른 경우: Advisory 내용 변경으로 보고 새로운 Version 생성

Bronze는 원본과 수집 사실을 보존하고, Silver는 정규화와 Version 관리를 담당한다. 이 책임 분리를 통해 Bronze는 재처리 가능한 원천 로그 역할을 유지한다.


---

## 10. Metadata 필드

### `_watermark.json`

| 필드 | 타입 | 내용 |
| --- | --- | --- |
| `source` | string | `"ghsa"` |
| `last_successful_watermark` | datetime | 마지막으로 수집 완료가 보장된 최종 종료 경계 |
| `updated_at` | datetime | 이 파일이 갱신된 시각 |

### `ghsa_{timestamp}_meta.json`

| 필드 | 타입 | 내용 |
| --- | --- | --- |
| `source` | string | `"ghsa"` |
| `batch_id` | string | 배치 식별자. `ghsa_{배치시각}` 형식 |
| `fetched_at` | datetime | 수집 시각. UTC 기준 |
| `file_name` | string | 대응하는 JSONL 파일명 |
| `format` | string | `"jsonl"` |
| `record_count` | integer | 수집 record 수 |
| `checksum` | string | Raw JSONL의 sha256 checksum |
| `schema_version` | string | `"bronze-v1"` |
| `source_url` | string | GitHub Advisories API endpoint |
| `page_count` | integer | API Pagination page 수 |
| `watermark_start` | datetime 또는 null | 증분 수집 시작 경계. Full Snapshot에서는 `null` |
| `watermark_end` | datetime | 해당 batch에서 정상 수집을 보장한 종료 경계 |
