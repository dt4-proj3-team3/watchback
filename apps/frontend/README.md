# Watchback Frontend

`tmp/ui-draft/Watchback UI 초안 (offline).html`의 디자인을 React 컴포넌트로 분리한 Next.js 애플리케이션이다. 대시보드와 재검토 화면은 Backend DB 또는 저장소 공통 Fixture를 선택해 사용한다.

## 실행

Node.js 20.9 이상이 필요하다.

```bash
cd apps/frontend
npm install
npm run dev
```

DB 모드를 사용하려면 `apps/frontend/.env.local`에 다음 서버 전용 환경변수를 설정한다. 브라우저에는 노출되지 않으며 Next.js Route Handler가 Backend 요청 헤더로 전달한다.

```dotenv
WATCHBACK_API_BASE_URL=http://localhost:8000
WATCHBACK_ORGANIZATION_ID=ff178e49-d218-50b7-bf56-ac3513330b99
WATCHBACK_USER_ID=7889d975-3d64-536f-8740-3d0a28ee3a1d
```

기본 데이터 소스는 `db`다. 설정 화면에서 사용자가 명시적으로 선택한 `db|demo` 값만 브라우저에 저장하며, DB 오류가 발생해도 Demo로 자동 전환하지 않는다. DB 모드의 패키지 화면은 실제 Alert·Candidate·Evidence와 lockfile에서 수집한 현재 버전을 사용한다. AI 도우미도 DB 모드에서만 동작하며 대화는 화면 세션에만 보존된다. Demo 데이터와 실제 DB 근거를 섞지 않는다.

브라우저에서 [http://localhost:3000](http://localhost:3000)을 연다.

## 화면 경로

- `/dashboard`: 대시보드
- `/review-cases`: 재검토 목록
- `/review-cases/{case_id}`: 재검토 상세
- `/repositories`: 저장소
- `/settings`: 설정

루트 경로 `/`는 `/dashboard`로 이동한다.

## 검증

```bash
npm run lint
npm test
npm run build
```
