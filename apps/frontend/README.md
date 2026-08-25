# Watchback Frontend

`tmp/ui-draft/Watchback UI 초안 (offline).html`의 디자인을 React 컴포넌트로 분리한 Next.js 애플리케이션이다. 화면 데이터는 저장소 공통 Fixture인 `data/demo/review-cases.json`을 사용한다.

## 실행

Node.js 20.9 이상이 필요하다.

```bash
cd apps/frontend
npm install
npm run dev
```

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
npm run build
```
