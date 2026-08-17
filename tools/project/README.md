# Sprint Issue Generator

`sprint-example.yml` 형식의 Sprint 계획으로 GitHub Parent Issue와 Sub-issue를 생성합니다.

사전 조건은 Git 저장소의 GitHub `origin` 또는 `GH_REPO=owner/repo`, `gh` 로그인, Python의 PyYAML입니다.

먼저 GitHub를 변경하지 않는 dry-run으로 전체 이슈와 라벨을 확인합니다.

```bash
python tools/project/create_sprint_issues.py --dry-run tools/project/sprint-example.yml
```

dry-run 결과를 검토하고 승인한 뒤 실제 생성을 실행합니다.

```bash
python tools/project/create_sprint_issues.py tools/project/sprint-example.yml
```

스크립트는 실제 생성 전에 YAML 전체의 필수값, 팀, 우선순위와 중복 제목을 검증합니다. 팀과 기본 라벨은 `.github/teams.yml`을 사용합니다. 우선순위는 제품 백로그와 동일한 `p0`, `p1`, `p2`이며, Projects의 custom field나 milestone은 수정하지 않습니다.
