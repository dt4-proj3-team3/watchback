# Watchback

Watchback은 누적된 Dependabot Alert를 관찰하고, 위험이나 조치 가능성이 달라져 다시 볼 가치가 생긴 항목과 이유를 알려주는 서비스입니다.

## 저장소 안내

| 경로 | 역할 |
| --- | --- |
| `apps/` | 독립적으로 실행하거나 배포하는 애플리케이션 |
| `fabric/workspace/` | API로 배포할 Microsoft Fabric 항목의 로컬 원본 |
| `infra/` | Azure와 Fabric 인프라 정의 |
| `docs/` | 제품·아키텍처·엔지니어링·계약 문서 |
| `tools/` | 개발과 프로젝트 관리 보조 도구 |

상세한 코드 배치 기준은 [Repository Layout](docs/engineering/repository-layout.md), Fabric 작업 절차는 [Fabric API 개발 워크플로](docs/engineering/fabric-api-workflow.md)를 따릅니다. 제품 요구사항은 [PRD](docs/product/prd.md), 시스템 구성은 [Technical Architecture](docs/architecture/technical-architecture.md)에서 확인합니다.
