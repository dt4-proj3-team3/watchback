# ADR-0010: 재검토 Case를 저장소와 CVE 단위로 관리

## 상태

Accepted

## 배경

Dependabot은 같은 의존성을 선언한 manifest와 lockfile에 별도 Alert를 만들 수 있다. Alert별 Case를 만들면 동일 저장소와 CVE가 목록에 반복되고 검토 상태와 활동도 나뉜다.

## 결정

- 재검토 Case의 업무 단위는 `organization + repository + CVE`로 한다.
- 원본 Dependabot Alert는 삭제하거나 합치지 않는다.
- Case는 대표 Alert를 하나 보존하고, 상세 API는 같은 저장소와 CVE에 연결된 Alert 전체를 제공한다.
- Candidate와 Evidence는 연결 Alert 전체를 통해 누적 조회한다.
- 서로 다른 저장소의 동일 CVE는 별도 Case로 유지한다.
- 중복 Case에 사용자 활동이나 외부 링크가 있으면 Migration이 임의 병합하지 않고 중단한다.

## 결과

manifest별 원본 추적은 유지하면서 목록의 중복 검토를 제거한다. Case 생성 서비스가 이 단위를 보장하며, DB의 `alert_id`는 호환성을 위한 대표 Alert다.
