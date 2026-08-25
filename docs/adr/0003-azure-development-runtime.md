# ADR-0003: Azure 개발 애플리케이션 실행 환경

- 상태: Accepted
- 날짜: 2026-08-25
- 관련 이슈/PR: #120
- 대체하는 ADR:
- 대체된 ADR:

## Context

Watchback은 Fabric 외부에서 Dependabot Alert를 수집하고 운영 DB와 Web 애플리케이션을 실행할 개발 환경이 필요하다. 현재 Backend는 API 계약 단계이고 Frontend는 데모 Fixture를 사용하지만, 동기화 Worker와 PostgreSQL은 실제 데이터로 검증할 수 있다. 개발 단계에서 운영 수준의 사설망과 자동 배포를 모두 도입하면 구현·운영 비용이 커진다.

## Decision

- Azure 리소스는 Bicep으로 선언하고 기존 `4dt_3rdproject_team_3` 리소스 그룹의 Korea Central에 배포한다.
- 이미지는 관리자 계정을 비활성화한 ACR에 저장하고 Container Apps는 사용자 할당 Managed Identity로 Pull한다.
- 비밀값은 RBAC 기반 Key Vault에 저장하고 Container Apps에서 Managed Identity로 참조한다.
- PostgreSQL Flexible Server는 개발용 Burstable SKU와 공개 네트워크를 사용한다. 로컬 접속은 개발자 공인 IP로 제한하고, Container Apps와 Job은 Azure 서비스 허용 규칙을 사용한다.
- Frontend와 Backend는 Container Apps Consumption으로 실행하고 최소 Replica를 0으로 둔다.
- DB 초기화와 Dependabot 동기화는 수동 Container Apps Job으로 실행한다. 공통 Job 모듈은 후속 Gold Sync Worker에서 재사용한다.
- 배포는 로컬 Azure CLI로 재현한다. GitHub Actions는 배포 경로와 권한이 안정된 뒤 별도 도입한다.
- Container Apps 로그는 Log Analytics에 수집한다. Application Insights는 리소스와 연결 정보만 준비하고 애플리케이션 계측은 후속 구현으로 남긴다.

## Alternatives

- Terraform은 별도 상태 저장과 도구 운영이 필요해 Azure 개발 환경 한 곳만 다루는 현재 범위에서는 선택하지 않았다.
- GHCR은 Azure가 GitHub 자격 증명을 추가로 관리해야 하므로 ACR보다 단순하지 않았다.
- PostgreSQL 사설 VNet 연결은 보안성이 높지만 개발자 접속, DNS와 Migration 실행 경로가 함께 복잡해져 개발 환경에서는 보류했다.
- Container Apps outbound IP를 개별 허용하면 현재 환경에서 161개 규칙을 관리해야 하므로 개발 환경에 비해 운영 복잡도가 크다.
- NAT Gateway의 고정 outbound IP는 범위를 좁힐 수 있지만 개발 환경에 네트워크 구성과 비용을 추가하므로 보류한다.
- 실제 구현이 없는 Gold Sync Job을 빈 컨테이너로 배포하지 않는다.

## Consequences

- 배포·정리 절차가 코드로 재현되며 이미지 Pull과 비밀 전달에 장기 자격 증명이 필요하지 않다.
- Azure 서비스 허용 규칙은 다른 Azure 고객의 리소스까지 네트워크 접근을 허용한다. PostgreSQL 인증과 TLS를 적용하되 이 선택은 개발 환경에만 한정한다.
- Container Apps outbound IP 변경을 추적하거나 개별 방화벽 규칙을 동기화하지 않아도 된다.
- 운영 환경은 PostgreSQL Private Access와 전용 네트워크를 사용해야 한다.
- Backend DB 조회와 Frontend DB 모드는 후속 구현 전까지 실제 E2E 흐름을 제공하지 않는다.
- App Insights 애플리케이션 추적은 SDK 또는 OpenTelemetry 계측을 추가하기 전까지 제공되지 않는다.

## Verification

- Bicep 재배포 시 같은 리소스가 유지되는지 확인한다.
- ACR 관리자 비활성화와 Managed Identity의 `AcrPull`, `Key Vault Secrets User` 역할을 확인한다.
- DB 초기화와 Dependabot Job을 실행하고 Migration, 기준 데이터, Alert 적재와 재실행 멱등성을 확인한다.
- Frontend와 Backend URL, PostgreSQL 방화벽 규칙, Log Analytics의 App·Job 로그를 확인한다.
- 비밀값이 Git 변경, 배포 출력과 애플리케이션 로그에 노출되지 않는지 검사한다.
