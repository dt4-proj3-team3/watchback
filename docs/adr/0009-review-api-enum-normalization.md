# ADR-0009: 재검토 API 위험 변화 enum 정규화

- 상태: Accepted
- 날짜: 2026-08-28
- 관련 이슈/PR: #105
- 대체하는 ADR:
- 대체된 ADR:

## Context

Gold는 변화 유형을 `EPSS_RISE`, `EPSS_TOP5_ENTRY`, `KEV_NEW`로, Evidence
신호를 `epss_score`, `epss_percentile`, `kev`로 제공한다. 기존 Web Demo와
화면은 D-30 의미가 포함된 별도 문자열을 사용해 실데이터에서 enum과 값 표시가
그대로 노출됐다.

## Decision

- DB에는 Gold 원본 값을 보존한다.
- Backend 공개 API에서 알려진 값을 다음 canonical 문자열로 변환한다.
  - `EPSS_RISE` → `epss_rise_d30`
  - `EPSS_TOP5_ENTRY` → `epss_top5_entry_d30`
  - `KEV_NEW` → `kev_new`
  - `epss_score` → `epss_score_d30`
  - `epss_percentile` → `epss_percentile_d30`
  - `kev` → `kev`
- `kev_added`는 필터 입력 호환 alias로만 받고 응답에서는 `kev_new`를 사용한다.
- 알려지지 않은 값은 API 전체를 실패시키지 않고 원본 문자열을 유지한다.
- DS가 제공한 `reason_summary`, `evidence_summary`는 API에서 치환하지 않는다.

## Alternatives

- Frontend에서만 변환하면 API 소비자마다 같은 규칙이 중복되므로 선택하지 않았다.
- Gold 저장값을 변경하면 생산자 원본 추적이 어려워 선택하지 않았다.
- 설명 문구까지 Backend에서 생성하면 DS 원문이 손실되므로 선택하지 않았다.

## Consequences

- Demo와 DB 모드가 같은 타입으로 화면 로직을 공유한다.
- 새 Gold 변화 유형은 원본 문자열로 노출되며 정식 지원 시 매핑을 추가해야 한다.
- 저장값과 공개 API 값이 다르므로 필터 입력은 Backend에서 역변환해야 한다.

## Verification

- 실제 Gold 형태의 목록·상세 API Fixture로 enum과 nullable GHSA를 검증한다.
- canonical·legacy 필터가 같은 저장값을 조회하는지 확인한다.
- Demo와 DB 응답이 동일한 화면 라벨과 값 형식을 사용하는지 확인한다.
