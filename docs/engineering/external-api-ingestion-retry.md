# External API Ingestion Retry


---

## 1. 목적

외부 위험 데이터 수집 과정에서 API 호출 실패를 상태 코드와 오류 유형에 따라 일관되게 처리하기 위한 공통 기준을 정의한다.

API 호출 실패는 모두 같은 방식으로 처리하지 않는다. 요청 자체가 잘못된 경우, API 제공자의 Rate Limit에 걸린 경우, 서버 측 일시 장애가 발생한 경우는 각각 원인과 복구 가능성이 다르다. 따라서 오류 유형에 따라 retry 여부와 대기 전략을 다르게 적용한다.

이 문서는 `fabric/workspace/ingestion/ingest_api.py`의 공통 retry 처리 기준을 설명하며, 각 수집 구현에서 오류 기록, Bronze 적재, batch metadata 기록을 설계할 때 참고한다.


---

## 2. 적용 범위

이 정책은 GHSA, EPSS, CISA KEV 등 외부 데이터 수집 API 호출에 적용한다.

- GHSA: GitHub API 기반 advisory 수집
- EPSS: FIRST EPSS 데이터 수집
- CISA KEV: CISA Known Exploited Vulnerabilities catalog 수집
- 향후 추가되는 외부 API 기반 Bronze ingestion 작업

이 문서는 API 호출 안정성에 대한 공통 기준만 다룬다. 데이터 정합성 검증, 스키마 계약, 중복 제거, 멱등성 검증, Bronze/Silver/Gold 계층별 저장 정책은 각 ingestion 구현 또는 `docs/contracts/`의 계층별 계약 문서에서 다룬다.


---

## 3. 핵심 구현

공통 구현은 `fabric/workspace/ingestion/ingest_api.py`의 `request_with_retry()`를 중심으로 한다.

`request_with_retry()`는 HTTP 요청을 실행하고, 응답 상태 코드나 네트워크 예외에 따라 성공 반환, 즉시 실패, 제한된 횟수 retry 중 하나를 선택한다.

주요 입력값은 다음과 같다.

| 인자 | 설명 |
| --- | --- |
| `method` | HTTP method |
| `url` | 요청 URL |
| `headers` | 요청 헤더 |
| `params` | Query parameter |
| `json` | JSON request body |
| `timeout` | 요청 timeout. 기본값은 5초 |
| `max_retries` | 최대 retry 횟수. 최초 요청은 제외하며 기본값은 3회 |
| `backoff_factor` | exponential backoff 계산에 사용하는 계수. 기본값은 `1.0` |
| `source` | API source 구분값. GitHub Rate Limit 처리가 필요한 경우 `ghsa` 또는 `kev` 사용 |

대기 시간 계산은 `_calculate_backoff()`에서 처리한다. 기본 방식은 exponential backoff에 jitter를 더하는 방식이다.

```text
wait_seconds = backoff_factor * (2 ** attempt) + jitter
```

GitHub Rate Limit 처리는 `_handle_github_rate_limit()`에서 담당한다. `Retry-After` 헤더가 있으면 해당 값을 우선 사용하고, `x-ratelimit-remaining`이 `0`이면 `x-ratelimit-reset` 시각까지 대기한다. 두 정보가 모두 없으면 Secondary Rate Limit으로 보고 기본 60초부터 backoff를 적용한다.


---

## 4. 재시도 정책 요약

### 상태 코드별 기본 정책

| 오류 유형 | Retry 여부 | 대기 전략 | 처리 기준 |
| --- | --- | --- | --- |
| `400 Bad Request` | Retry하지 않음 | 해당 없음 | 요청 body, URL, ID, 입력 데이터 상태를 우선 확인하고 오류를 기록한다. |
| `404 Not Found` | Retry하지 않음 | 해당 없음 | 요청한 리소스, URL, 권한, 데이터 상태를 확인하고 오류를 기록한다. |
| `429 Too Many Requests` | Retry | `Retry-After` 우선, 없으면 Backoff + Jitter | Rate Limit 상황으로 보고 제한된 횟수만 retry한다. |
| `5xx` | Retry | Backoff + Jitter | 서버 측 일시 장애 가능성이 있으므로 제한된 횟수만 retry한다. |
| Timeout | Retry | Backoff + Jitter | 네트워크 또는 응답 지연으로 보고 제한된 횟수만 retry한다. |
| ConnectionError | Retry | Backoff + Jitter | 연결 실패로 보고 제한된 횟수만 retry한다. |

### `400` / `404`

`400 Bad Request`는 요청 형식이나 입력값에 문제가 있는 경우이고, `404 Not Found`는 요청한 리소스를 찾을 수 없는 경우이다.

이 경우 동일한 요청을 그대로 다시 보내도 해결되지 않을 가능성이 높기 때문에 단순 retry 대상이 아니다. 요청 body, URL, ID, 입력 데이터 상태를 우선 확인한다.

기본 정책은 요청 또는 데이터 상태 확인, 오류 로그 기록, retry하지 않음이다.

### `429 Too Many Requests`

`429`는 클라이언트 요청이 많아 API 제공자의 Rate Limit에 걸린 상황이다. 요청 내용 자체가 틀린 것은 아니므로 일정 시간 대기한 뒤 retry할 수 있다.

응답 헤더에 `Retry-After`가 제공되면 서버가 알려준 대기 시간을 우선 적용한다. `Retry-After`가 없다면 exponential backoff와 jitter를 조합하여 재시도 간격을 결정한다.

기본 정책은 `429` 감지, `Retry-After` 확인, 있으면 해당 시간 대기, 없으면 Backoff + Jitter 적용, 제한된 횟수 retry이다.

### `5xx`

`500`, `502`, `503`, `504` 등의 `5xx`는 서버 또는 서버 측 처리 경로에서 발생한 오류이다.

일시적인 장애일 가능성이 있으므로 Backoff + Jitter를 적용한 뒤 제한된 횟수만 retry한다. 최대 retry 횟수를 초과하면 최종 실패로 기록한다.

기본 정책은 `5xx` 감지, Backoff + Jitter, 제한된 횟수 retry, 계속 실패하면 최종 실패 기록이다.

### GitHub Rate Limit 정책

GHSA와 KEV 수집에서 GitHub API를 호출하는 경우 `source="ghsa"` 또는 `source="kev"`를 전달해 GitHub Rate Limit 처리를 적용한다.

| 상황 | 처리 |
| --- | --- |
| `403` + `x-ratelimit-remaining=0` | Primary Rate Limit으로 보고 `x-ratelimit-reset`까지 대기 후 retry |
| `403` + message에 `secondary rate limit` 포함 | Secondary Rate Limit으로 보고 `Retry-After` 우선, 없으면 최소 60초 기반 Backoff + Jitter 후 retry |
| `403` 중 Rate Limit이 아닌 인증/권한 오류 | Retry하지 않고 즉시 실패 |
| `429` | GitHub Rate Limit으로 보고 `Retry-After` 우선, 없으면 GitHub Rate Limit 정책에 따라 retry |
| 반복 Rate Limit | Backoff를 적용하되 `max_retries`를 넘으면 최종 실패 |

GitHub API 호출 시 인증 없이 공개 데이터 조회가 가능한 경우도 있지만, 팀에서는 공통 GitHub 인증 구조와 Rate Limit 완화를 위해 PAT 사용을 고려할 수 있다. 인증/권한 문제, `User-Agent` 누락, Rate Limit은 모두 `403`으로 관측될 수 있으므로 응답 헤더와 메시지를 함께 확인한다.

### Source별 고려사항

| 항목 | GHSA | EPSS | KEV |
| --- | --- | --- | --- |
| 주요 호출 방식 | GitHub API | 일별 CSV 또는 API | CISA KEV catalog |
| 기본 요청 주기 | 1일 1회 | 1일 1회 CSV | 1시간 1회 |
| `400` | 요청 또는 데이터 상태 확인 후 오류 기록 | 요청 또는 데이터 상태 확인 후 오류 기록 | 요청 또는 데이터 상태 확인 후 오류 기록 |
| `404` | URL, 인증, 권한, 리소스 상태 확인 후 retry하지 않음 | 요청 또는 데이터 상태 확인 후 오류 기록 | 요청 또는 데이터 상태 확인 후 오류 기록 |
| `403` | 인증/권한, `User-Agent`, Primary/Secondary Rate Limit 여부 확인 | 해당 없음 | GitHub API 사용 시 GHSA와 동일한 기준 적용 |
| `429` | `Retry-After` 우선, 없으면 GitHub Rate Limit 정책 적용 | `Retry-After`가 있으면 해당 시간 대기, 없으면 공통 retry 처리 | `Retry-After`가 있으면 해당 시간 대기, 없으면 공통 retry 처리 |
| `Retry-After` | 제공 시 우선 적용 | 공식 문서 기준 미확인 | 공식 문서 기준 미확인 |
| `5xx` | 공통 retry 처리 | 공통 retry 처리 | 공통 retry 처리 |
| Timeout | 공통 retry 처리 | 공통 retry 처리 | 공통 retry 처리 |
| Pagination | `per_page=100`과 `Link: rel="next"` 확인 | 현재 CSV 방식에는 불필요 | 현재 CSV 방식에는 불필요 |
| 후속 개선 후보 | Pagination 완전성 검증 | `Last-Modified` 활용 검토 | 전체 Snapshot 보존과 변경분 MERGE 방식 논의 |

EPSS는 전체 데이터를 매일 적재하는 경우 Daily CSV를 사용할 수 있으므로 API pagination이 필요하지 않을 수 있다. KEV도 현재 catalog 단위 수집에서는 pagination이 필요하지 않지만, 변경 감지와 저장 방식은 전체 Snapshot 보존 또는 변경분 MERGE 중 어떤 방식을 채택할지 별도로 결정한다.

공통 retry 처리는 API 호출 실패에 대한 복구 가능성을 높이는 장치이며, 수집 작업의 최종 성공을 보장하지 않는다. 각 ingestion 구현은 최종 실패 시 source, URL, 상태 코드, retry 횟수, batch id, 기준 시점 등을 남겨 재실행과 장애 분석이 가능하도록 해야 한다.
