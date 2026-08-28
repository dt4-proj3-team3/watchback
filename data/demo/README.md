# Watchback 데모 데이터

## 배경

Sprint 1 데모는 한 회사가 운영하는 여러 저장소에서 실제 Dependabot Alert를 수집하고, 외부 위험 변화 후보와 연결된 재검토 Case를 화면에 보여주는 것을 목표로 한다.

이를 위해 실행·배포하지 않는 취약 의존성 전용 FE·BE Lab을 구성했다. 중요도가 낮은 Alert 수를 늘리는 것이 아니라, Critical·High 또는 KEV·EPSS 변화 검토 가치가 있는 CVE를 충분히 확보하는 것이 원래 기준이었다. 최종 후보 판정은 이 데이터에 포함하지 않는다.

이 디렉터리는 다음 두 용도로 남긴 고정 데이터다.

- FE·BE Lab에 어떤 취약점을 의도적으로 넣었는지 확인
- 실제 연동 전에도 목록·상세 화면과 API 계약을 동일한 데이터로 검증

## 파일

| 파일 | 내용 |
| --- | --- |
| [`vulnerabilities.json`](vulnerabilities.json) | Lab의 CVE 16개와 실제 Dependabot Alert 31건 |
| [`review-cases.json`](review-cases.json) | 확인된 S1 위험 신호가 있는 실제 Alert로 만든 목록·빈 목록·상세 화면용 응답 |

`vulnerabilities.json`이 취약점과 Alert 정보의 기준이고, `review-cases.json`은 그중 일부를 사용한 파생 데이터다.

## FE Lab

대상 저장소는 `dt4-proj3-team3/watchback-vulnerable-fe-lab`이다. FE·풀스택 환경을 가정해 `next@15.2.2`, `vite@6.2.2`, `react-server-dom-webpack@19.2.0`을 고정했다.

`기대 위험 신호`는 CISA KEV와 FIRST EPSS 실제 이력을 바탕으로 예상한 결과다. EPSS는 2025-03-21부터 2026-08-20까지 매일의 값을 30일 전과 비교했다. GHSA 패치 변화는 과거 Snapshot을 아직 확보하지 않아 판정하지 않았다.

| 패키지 | 고정 버전 | CVE / GHSA | 중요도 | 최초 수정 버전 | 기대 위험 신호 |
| --- | --- | --- | --- | --- | --- |
| `next` | `15.2.2` | `CVE-2025-29927`<br>`GHSA-f82v-jwr5-mffw` | Critical | `15.2.3` | 2025-04-21 EPSS가 크게 상승하고 상위 5%에 진입 |
| `next` | `15.2.2` | `CVE-2026-44578`<br>`GHSA-c4j6-fc7j-m34r` | High | `15.5.16` | 2026-06-13 EPSS 급상승, 2026-06-23 상위 5% 진입 |
| `vite` | `6.2.2` | `CVE-2025-30208`<br>`GHSA-x574-m823-4x7w` | Medium | `6.2.3` | 2025-04-24 EPSS가 크게 상승하고 상위 5%에 진입 |
| `vite` | `6.2.2` | `CVE-2025-31125`<br>`GHSA-4r4m-qw57-chr8` | Medium | `6.2.4` | 2025-05-01 EPSS 급상승, 2026-01-22 KEV 신규 등재, 다음 날 상위 5% 진입 |
| `vite` | `6.2.2` | `CVE-2025-31486`<br>`GHSA-xcj6-pq6g-qj4x` | Medium | `6.2.5` | 2025-11-18 EPSS 급상승. 2026-06-15 상위 5% 진입은 후보를 유지하고 EPSS v5 모델 전환 주석과 함께 표시 |
| `vite` | `6.2.2` | `CVE-2026-39363`<br>`GHSA-p9ff-h696-f583` | High | `6.4.2` | 2026-05-14 EPSS 급상승 |
| `react-server-dom-webpack` | `19.2.0` | `CVE-2025-55182`<br>`GHSA-fv66-9v8q-g76r` | Critical | `19.2.1` | 2025-12-05 KEV 신규 등재, 2026-01-03 EPSS 급상승과 상위 5% 진입 |
| `react-server-dom-webpack` | `19.2.0` | `CVE-2025-55183`<br>`GHSA-925w-6v3x-g4j4` | Medium | `19.2.2` | 2026-01-11 EPSS 급상승 |
| `react-server-dom-webpack` | `19.2.0` | `CVE-2025-55184`<br>`GHSA-2m3v-v2m8-q956` | High | `19.2.2` | 2026-01-11 EPSS 급상승 |

FE Snapshot에는 고유 CVE 9개와 Alert 17건(Open 11건, Fixed 6건)이 있다.

같은 Vite CVE에 Alert가 여러 건인 것은 루트 `package-lock.json`과 전이 의존성 검증용 manifest가 함께 있기 때문이다.

## BE Lab

대상 저장소는 `dt4-proj3-team3/watchback-vulnerable-be-lab`이다. `novalink/ai-platform-api`라는 Python 3.10 기반 AI 모델 서빙·LLM 게이트웨이 Backend를 가정해 Django, BentoML, LiteLLM의 취약 버전을 고정했다.

각 CVE는 `pyproject.toml`과 `uv.lock`에서 각각 탐지되어 Alert 2건씩 존재한다.

BE는 EPSS 변화만 있는 사례와 KEV·EPSS가 함께 변한 사례를 모두 포함한다. 아래 변화는 모두 실제 CISA KEV와 FIRST EPSS 이력에서 확인했으며, 2026-06-15 모델 교체만으로 설명되는 사례는 포함하지 않았다.

| 패키지 | 고정 버전 | CVE / GHSA | 중요도 | 최초 수정 버전 | 기대 위험 신호 |
| --- | --- | --- | --- | --- | --- |
| `Django` | `4.2.20` | `CVE-2026-1207`<br>`GHSA-mwm9-4648-f68q` | High | `4.2.28` | 2026-03-07 EPSS 급상승, 2026-07-24 상위 5% 진입 |
| `bentoml` | `1.4.2` | `CVE-2025-27520`<br>`GHSA-33xw-247w-6hmc` | Critical | `1.4.3` | 2025-05-05 EPSS 급상승과 상위 5% 진입 |
| `bentoml` | `1.4.2` | `CVE-2025-32375`<br>`GHSA-7v4r-c989-xh26` | Critical | `1.4.8` | 2025-05-10 EPSS 급상승과 상위 5% 진입 |
| `litellm` | `1.81.16` | `CVE-2026-35029`<br>`GHSA-53mr-6c8q-9789` | High | `1.83.0` | 2026-05-07 EPSS 급상승, 2026-05-18 상위 5% 진입 |
| `litellm` | `1.81.16` | `CVE-2026-40217`<br>`GHSA-wxxx-gvqv-xp7p` | High | `1.83.10` | 2026-07-01 EPSS 급상승 |
| `litellm` | `1.81.16` | `CVE-2026-42208`<br>`GHSA-r75f-5x8p-qvmc` | Critical | `1.83.7` | 2026-05-08 KEV 신규 등재, 2026-06-07 EPSS 급상승과 상위 5% 진입 |
| `litellm` | `1.81.16` | `CVE-2026-42271`<br>`GHSA-v4p8-mg3p-g94g` | High | `1.83.7` | 2026-06-08 KEV 신규 등재, 2026-06-09 EPSS 급상승과 상위 5% 진입 |

BE Snapshot에는 고유 CVE 7개와 Open Alert 14건이 있다.

확인된 개별 위험 변화는 FE 9개와 BE 7개로 총 16개 CVE다. 현재 Open Alert와 연결하면 FE 11건과 BE 14건으로 최대 25개 Case를 구성할 수 있다.

`review-cases.json`은 이 중 FE의 `CVE-2025-29927`, `CVE-2026-44578`, `CVE-2025-31125`, `CVE-2026-39363`, `CVE-2025-55182`와 BE의 `CVE-2026-1207`, `CVE-2025-27520`, `CVE-2026-35029`, `CVE-2026-42208`을 사용한다. FE 6건과 BE 4건, 총 10개 Case로 구성했으며 EPSS 단독 변화와 KEV·EPSS 복합 변화를 모두 포함한다. 모두 High·Critical이며, `CVE-2025-31125`만 실제 KEV 등재가 확인된 Medium 예외다.

## 실제 값과 합성 값

실제 GitHub Snapshot에서 가져온 값:

- 저장소 이름
- Alert 번호·상태·manifest·패키지·의존성 관계
- GHSA·CVE·중요도·CVSS·영향 버전·최초 수정 버전
- GitHub 생성·수정 시각과 Alert URL

공식 위험 데이터에서 계산한 값:

- CISA KEV 등재 여부와 등재일
- FIRST EPSS D-30 점수·percentile 변화
- 현재 후보 선정 기준으로 예상한 위험 변화와 S1 포함 여부

화면과 API 확인을 위해 합성한 값:

- Review Case ID·상태·사유·시각
- Candidate·Evidence·Batch ID
- Candidate와 Case의 화면 표시용 우선순위
- Gold Batch 전달 시각
- 화면 표시용 조직명·저장소명·중요도

위험 신호의 종류·발생일·전후 값은 공식 소스로 계산한 사전 기댓값이며, 실제 DS 평가 결과는 아니다. DS 결과와 다르면 소스 시점과 규칙 적용 결과를 다시 대조한다.


## Snapshot 기준

- GitHub 수집 시각: FE `2026-08-21T06:52:40Z`, BE `2026-08-24T02:52:00Z`
- GitHub REST API 버전: `2022-11-28`
- EPSS 검증 범위: `2025-03-21`~`2026-08-20`
- KEV Catalog 버전: `2026.08.20`
- KEV 소스: [CISA Known Exploited Vulnerabilities Catalog](https://www.cisa.gov/known-exploited-vulnerabilities-catalog)
- EPSS 소스: [FIRST EPSS API](https://api.first.org/epss/)
- 소스 변동 기준일: [FIRST EPSS 데이터 및 모델 이력](https://www.first.org/epss/data)
