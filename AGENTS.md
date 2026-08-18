# Watchback Agent Instructions

## 작업 원칙

- 작업 전 `docs/README.md`와 요청에 직접 관련된 문서를 읽는다.
- 파일을 생성하거나 이동하기 전 [Repository Layout](docs/engineering/repository-layout.md)을 읽고 코드 배치 규칙을 따른다.
- 현재 저장소에 없는 구조나 실행 방법을 추측하지 않는다.
- 변경 범위를 요청에 필요한 수준으로 유지하고, 무관한 정리는 하지 않는다.
- 사용자 변경사항을 보존하고 확인하지 못한 결과를 완료로 보고하지 않는다.
- 코드·설계·리뷰처럼 판단이 필요한 작업에는 [Karpathy Guidelines](skills/karpathy-guidelines/SKILL.md)를 적용한다.

## 제품 기준

- 제품 범위의 원본은 `docs/product/prd.md`다.
- 우선순위와 사용자 수용 기준은 `docs/product/product-backlog.md`를 따른다.
- 현재 Sprint의 실행 범위와 팀 경계는 `docs/product/`의 해당 Sprint 백로그를 따른다.
- 팀별 세부 작업은 해당 Sprint의 팀별 작업 문서를 따른다.
- Watchback은 실제 악용 여부나 패치 안전성을 확정하는 제품으로 표현하지 않는다.

## 팀 경계

- DE: 외부 위험 데이터 수집, Bronze·Silver·Gold 계층과 전달 경로를 담당한다.
- DS: Silver의 외부 위험 이력에서 고객과 독립적인 위험 변화 후보와 근거를 만든다.
- Web: Gold 후보와 조직의 Dependabot Alert를 연결하고 Case·검토·조치 흐름을 제공한다.
- 경계를 바꾸거나 여러 팀의 계약에 영향을 주는 변경은 계약 문서 또는 ADR로 먼저 명시한다.

## Git 작업

- Git 저장소에서는 작업 전 브랜치와 변경 상태를 확인한다.
- `main`에서 직접 구현하거나 push하지 않고 `type/짧은-설명` 브랜치를 사용한다.
- 관련 이슈가 있으면 `type/이슈번호-짧은-설명` 형식을 권장한다.
- 커밋은 한 목적씩 `type: 한국어 요약` 형식으로 작성한다.
- 권장 type은 `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `spike`다.
- PR은 `.github/pull_request_template.md`를 기준으로 작성한다.

## 이슈와 검증

- GitHub Issue를 생성하거나 수정할 때는 [GitHub Issues](skills/github-issues/SKILL.md)를 적용한다.
- 이슈는 `.github/ISSUE_TEMPLATE/`에서 팀에 맞는 템플릿을 사용한다.
- 저장소의 Issue Form이 GitHub Issues 스킬의 범용 템플릿보다 우선한다.
- Story와 여러 Story를 지원하는 Technical Task는 같은 계층의 이슈로, 실제 실행 단위는 Sub-issue로 관리한다.
- 이슈에는 목적, 범위, 기대 결과, 완료 기준과 확인 관점을 적고 구현 방법을 불필요하게 고정하지 않는다.
- Sprint 이슈를 일괄 생성할 때는 `tools/project/create_sprint_issues.py --dry-run <sprint.yml>`으로 전체 결과를 먼저 검토하고, 사용자 승인 후 실제 생성을 실행한다.
- 데이터 변경은 건수뿐 아니라 기준 시점, 샘플 내용, 키·필드 매핑, 누락·중복·타입, 재실행 결과를 확인한다.
- 문서만 변경한 경우 링크, 경로, 용어와 문서 간 모순을 직접 검토한다.

## Fabric 작업

- Fabric Notebook이나 Data Pipeline을 생성·수정·실행할 때는 [Fabric API 개발 워크플로](docs/engineering/fabric-api-workflow.md)를 따른다.
- GitHub의 로컬 파일을 코드 원본으로 사용하고 Fabric 워크스페이스는 실행·검증 환경으로 사용한다.
- 원격 변경 전에 워크스페이스와 Item을 조회해 정확한 ID와 최신 정의를 확인한다.
- API 배포의 Operation 상태와 원격 실행의 Job 상태·`failureReason`·`exitValue`를 확인한다.
- Fabric 웹 편집 내용과 로컬 변경을 임의로 덮어쓰지 않으며, 공유 워크스페이스의 같은 Item을 동시에 변경하지 않는다.
- 토큰과 자격 증명을 파일이나 로그에 남기지 않고, 환경별 ID를 Notebook 코드에 하드코딩하지 않는다.
- Lakehouse 스키마 변경은 `fabric/workspace/migrations/`의 Migration Notebook으로 실행하고 관련 `docs/contracts/` 문서를 같은 변경에서 갱신한다.

## ADR와 계약

- 아키텍처, 데이터 소유권, 스키마 경계, 외부 API, 보안·비용·성능에 영향을 주는 결정은 `docs/adr/`에 기록한다.
- ADR은 `docs/adr/0000-template.md`를 복사해 `NNNN-짧은-제목.md`로 작성한다.
- 팀 간 데이터 구조 변경은 생산자·소비자와 호환성 영향을 계약 문서 또는 관련 이슈에 기록한다.
