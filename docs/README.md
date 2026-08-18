# Watchback 문서 안내

작업을 시작할 때 이 문서를 진입점으로 사용하고, 필요한 문서만 추가로 읽습니다.

| 영역 | 위치 | 역할 |
| --- | --- | --- |
| 제품 | [`product/`](product/) | PRD, 제품 백로그, Sprint와 팀별 작업 범위 |
| 아키텍처 | [`architecture/`](architecture/) | 시스템 구성요소, 데이터 흐름과 책임 경계 |
| 엔지니어링 | [`engineering/`](engineering/) | 저장소 구조와 코드 배치 규칙 |
| ADR | [`adr/`](adr/) | 중요한 기술·운영 결정과 그 결과 |
| 계약 | [`contracts/`](contracts/) | DE·DS·Web 사이의 데이터·인터페이스 계약 문서 |

## 문서 원본 원칙

- 제품 요구와 비목표: `product/prd.md`
- 사용자 스토리와 수용 기준: `product/product-backlog.md`
- 현재 Sprint의 목표, Story, Technical Task와 팀 경계: `product/`의 해당 Sprint 백로그
- 저장소 구조와 코드 배치 규칙: `engineering/repository-layout.md`
- Fabric 항목의 생성·배포·실행 절차: `engineering/fabric-api-workflow.md`
- 구현 중 확정되는 API와 스키마: 코드와 버전 관리되는 계약 문서
- 중요한 결정의 배경과 결과: `adr/`

존재하지 않는 구현이나 운영 절차는 완료된 것처럼 문서화하지 않습니다. 문서 간 내용이 충돌하면 위 원본을 우선하고 충돌을 명시적으로 해결합니다.
