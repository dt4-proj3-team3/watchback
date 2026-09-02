# ADR-0012: 패키지 조치 그룹과 Case 이력을 분리

- 상태: Proposed
- 날짜: 2026-09-01
- 관련 이슈/PR:
- 대체하는 ADR:
- 대체된 ADR:

## Context

사용자는 같은 패키지 업데이트로 함께 해결할 수 있는 저장소와 Alert를 한 번에 검토해야 한다. 반면 기존 Review Case는 ADR-0010에 따라 `organization + repository + CVE` 단위로 검토 활동과 위험 변화 이력을 보존한다. 패키지 화면을 Case 자체로 대체하면 여러 저장소의 일괄 조치와 manifest별 부분 완료를 함께 표현하기 어렵다.

## Decision

- 패키지 조치 화면의 상위 그룹은 `organization + ecosystem + package_name`으로 계산한다.
- `package_name`은 생태계 식별 규칙으로 정규화한다. 초기 지원 범위에서 PyPI는 PEP 503 방식으로 대소문자와 `-_.` 구분을 통일하고 npm은 소문자로 통일한다.
- 각 그룹 아래의 조치 대상은 `repository + ecosystem + dependency project root`로 묶고 Alert·CVE·기존 Review Case를 연결한다.
- 같은 dependency project root의 선언 파일과 lockfile은 하나의 조치 대상에 속한다. 예를 들어 `pyproject.toml`과 `uv.lock`, `package.json`과 `package-lock.json`은 한 PR 범위로 취급하되 원본 manifest 경로와 Alert는 모두 보존한다.
- 같은 저장소라도 dependency project root가 다르면 별도 조치 대상으로 유지한다.
- Review Case는 기존 `organization + repository + CVE` 단위를 유지하며 위험 변화와 검토 이력을 소유한다.
- 위험 수용과 조치 요청은 `저장소 + dependency project root`를 기본 실행 단위로 기록한다. 패키지 전체 처리는 현재 Open 대상들을 한 요청에서 선택한 일괄 실행으로 표현한다.
- 패키지 조치 상태는 `검토 필요(needs_review)`, `위험 수용(accepted)`, `해결됨(resolved)` 세 가지로 계산한다.
- Open Alert의 현재 Candidate와 일치하는 활성 위험 수용 기록이 있으면 `위험 수용`, 일치하지 않으면 `검토 필요`로 본다. 모든 Alert가 GitHub에서 Open이 아니면 `해결됨`으로 본다.
- 위험 수용은 `Alert + Candidate` Snapshot에 적용한다. 나중에 추가된 Alert·manifest나 새 Candidate는 과거 결정을 상속하지 않고 `검토 필요`로 다시 열린다.
- 위험 수용 사유는 `호환성 문제로 보류`, `현재 영향 낮음`, `기타` 중 하나로 저장하고, `기타`에만 자유 입력 사유를 요구한다.
- 사용자가 `재검토 열기`를 선택하면 해당 저장소·dependency project root의 활성 위험 수용을 삭제하지 않고 취소 시각과 작업자를 기록한다. 전체 재검토는 모든 활성 대상을 같은 방식으로 취소한다.
- GitHub Alert 상태와 Watchback의 검토·조치 상태를 별도 값으로 보존한다.
- 자동조치 PR 병합은 `PR 병합 완료`로 기록하며 Dependabot이 확인한 `fixed` 상태와 동일시하지 않는다.
- 초기 자동조치 API는 사용자가 명시적으로 선택한 npm `runtime` 직접 의존성의 동일 major·minor patch 업데이트만 허용한다.
- Backend는 GitHub 기본 브랜치의 `package.json`과 `package-lock.json`을 임시 디렉터리에서 갱신하고, 스크립트를 실행하지 않는다. 변경 파일은 두 파일로 제한하며 lockfile dependency entry가 20개를 초과해 추가·제거되면 중단한다.
- 저장소·dependency project root마다 결정적 브랜치를 사용해 열린 PR을 재사용하고, PR URL·head SHA·현재/목표 버전·변경 파일을 조치 이력에 저장한다.
- PR 생성은 자동 병합이나 패치 안전성 확정을 의미하지 않으며, 병합 전 CI와 애플리케이션 테스트를 요구한다.
- 사용자가 병합을 명시적으로 요청하면 저장된 PR 번호·head ref·head SHA가 현재 GitHub PR과 일치하고 변경 파일이 허용 범위 안이며, 존재하는 GitHub Check가 모두 완료·성공한 경우에만 squash merge한다. Check가 구성되지 않은 Lab 저장소는 PR 변경 범위 검증 후 병합할 수 있지만 운영 정책에서는 필수 Check 구성이 선행되어야 한다.
- 저장소별 병합 결과는 매 PR 직후 저장하고, 전체 PR이 병합된 경우에만 조치 상태를 `pr_merged`로 변경한다. Dependabot의 `fixed` 확인 전에는 `completed`로 처리하지 않는다.
- 병합 API는 연결된 Dependabot Alert만 GitHub에서 다시 조회해 `fixed`와 `fixed_at`을 확인한다. 확인된 원천 값을 운영 DB에 제한적으로 동기화하고 전부 fixed이면 `completed`, 제한 시간 안에 확인되지 않으면 `verification_pending`으로 기록한다. 일반적인 전체 Alert 수집은 기존 Dependabot Sync Job이 계속 담당한다.

## Alternatives

- Case grain을 패키지로 변경하면 기존 CVE 변화 이력과 활동의 의미가 바뀌고 Migration 범위가 커져 선택하지 않았다.
- 패키지 조치 시 연결된 Case를 즉시 모두 해결 처리하면 다른 manifest의 미처리 Alert까지 완료로 오인할 수 있어 선택하지 않았다.
- 저장소별 패키지 그룹은 한 번의 업데이트로 여러 저장소를 조치하는 제품 흐름을 제공하지 못해 상위 그룹으로 사용하지 않는다.

## Consequences

- 패키지 화면은 여러 저장소를 묶지만 감사 이력과 원본 Alert 추적은 유지된다.
- 안전한 쓰기 작업을 위해 그룹 조치와 하위 대상 연결을 저장하는 최소 스키마가 필요하다.
- 기존 Review Case API와 데이터는 호환성을 유지할 수 있다.

## Verification

- 같은 패키지가 여러 저장소에 존재하면 한 그룹과 여러 대상으로 조회되는지 확인한다.
- 같은 dependency project root의 선언 파일·lockfile이 한 대상으로 묶이고 manifest별 Alert가 소실되지 않는지 확인한다.
- 같은 저장소의 서로 다른 dependency project root가 분리되는지 확인한다.
- 위험 수용, 수용 취소와 신규 Alert·Candidate 유입 후 상태를 확인한다.
- PR 병합 상태와 GitHub Alert 상태가 서로 덮어쓰이지 않는지 확인한다.
- 같은 자동조치 요청을 재실행해도 PR이 중복 생성되지 않고 기존 이력을 반환하는지 확인한다.
