# ADR-0013: GitHub lockfile에서 실제 의존성 버전 관찰

- 상태: Proposed
- 날짜: 2026-09-01
- 관련 이슈/PR:
- 대체하는 ADR:
- 대체된 ADR:

## Context

Dependabot Alert의 영향 버전 범위와 권장 수정 버전만으로는 저장소가 실제 사용하는 버전을 알 수 없다. 패키지 조치 후보와 업데이트 범위를 설명하려면 GitHub 기본 브랜치의 manifest와 lockfile에서 해석된 버전을 별도로 관찰해야 한다.

## Decision

- Dependabot 동기화 과정에서 GitHub 기본 브랜치의 manifest와 연결된 lockfile을 읽는다.
- manifest의 선언 제약은 실제 사용 버전으로 간주하지 않고 lockfile의 해석된 버전을 우선한다.
- 관찰 키는 `repository + manifest_path + commit_sha + ecosystem + package_name`으로 한다.
- 결과에는 해석된 모든 버전, 원본 파일 경로와 blob SHA, 관찰 시각과 해석 상태를 보존한다.
- 같은 패키지의 버전이 여러 개면 하나를 임의 선택하지 않고 모두 보존한다.
- 지원하지 않는 형식, 파일 부재와 파싱 실패는 `확인 불가` 계열 상태로 명시하며 영향 버전 범위로 추정하지 않는다.
- 동일 실행에서는 `repository + source_path + commit_sha`로 파일 조회를 재사용한다.

## Alternatives

- Dependabot의 영향 범위를 현재 버전으로 표시하는 방식은 의미가 다르므로 선택하지 않았다.
- manifest 선언만 읽는 방식은 범위 지정과 실제 해석 버전을 혼동하므로 선택하지 않았다.
- 저장소 전체 SBOM만 사용하는 방식은 manifest별 연결이 불명확할 수 있어 보조 검증 수단으로만 고려한다.

## Consequences

- 화면에서 실제 사용 버전과 권장 수정 버전을 구분할 수 있다.
- package manager별 lockfile parser와 GitHub Contents API 호출이 필요하다.
- commit SHA가 바뀐 경우에만 다시 해석하도록 호출량을 줄일 수 있다.

## Verification

- npm과 Python Lab 저장소의 실제 lockfile 버전을 샘플로 대조한다.
- 다중 버전, 파일 없음, 미지원 형식과 잘못된 파일을 검증한다.
- 같은 commit SHA 재실행에서 결과가 달라지거나 불필요한 중복이 생기지 않는지 확인한다.
