# A2A Security Dashboard – Agents

간단한 에이전트 목록/등록 UI와 Express 기반 API 서버입니다. 에이전트 카드는 로컬 파일(`data/agents.json`)에 저장되며, 관리자 토큰 검증을 외부 `/users/me` 엔드포인트로 프록시합니다.

## 빠른 시작
- 요구 사항: Node.js 18+ (또는 Python 3로 정적 서빙만 가능)
- 설치: `npm install`
- 실행: `npm start` (기본 포트 `3000`)
- 접속: 브라우저에서 `http://localhost:3000`

Python으로 정적 서빙만 할 수도 있습니다(API 미동작):
- `python3 serve.py` → `http://localhost:3000`

## 주요 파일
- `agents.html`: 에이전트 UI 페이지 (리스트, 등록 버튼 등)
- `style.css`: UI 스타일
- `server.js`: Express 앱 엔트리, 정적 파일 + 라우터 연결
- `agents-create.js`: `/api` 라우트, 토큰 검증/등록/목록, 파일 저장
- `data/agents.json`: 에이전트 데이터 저장 파일(자동 생성)

## 실행 옵션 (환경변수)
- `PORT`: 서버 포트 (기본 `3000`)
- `ADMIN_EMAIL`: 관리자 이메일 (기본 `admin@example.com`)
- `USERME_DIRECT_URL`: 토큰 검증 대상 (기본 `http://127.0.0.1:8000/users/me`)

예시:
```
PORT=3000 ADMIN_EMAIL=admin@example.com \
USERME_DIRECT_URL=http://127.0.0.1:8000/users/me npm start
```

## 토큰 검증 흐름
- 프론트엔드: 등록 버튼 클릭 → JWT 입력 → `/api/auth/me`로 프록시 검증
- 서버: `USERME_DIRECT_URL`로 GET 요청(헤더: `Authorization: Bearer <token>`)
  - 200 + `{ "email": "..." }` → 유효
  - 401 + `{ "detail": "Invalid token" }` → 무효
- 관리자 체크: 응답 이메일이 `ADMIN_EMAIL`과 동일해야 등록 가능

개발/로컬 테스트 시, 간단한 모킹 서버가 필요합니다. 예: `/users/me`에서 200과 `{"email":"admin@example.com"}` 응답.

## API
- GET `/api/agents`
  - 응답: `{ "agents": [ { "name": string, "status": "Active", "card": object? } ] }`
- POST `/api/agents` (관리자 전용)
  - 헤더: `Authorization: Bearer <JWT>`
  - 바디(JSON): 아래 최소 스키마를 만족해야 합니다.
    - `name`: string (필수)
    - `url`: string (필수)
    - `version`: string (필수)
    - `protocolVersion`: string (필수)
    - `capabilities`: object (필수)
  - 예시 바디:
```
{
  "name": "Agent1",
  "description": "",
  "protocolVersion": "1.0",
  "url": "http://localhost:10001",
  "version": "1.0.0",
  "capabilities": {"streaming": true, "pushNotifications": true, "stateTransitionHistory": false}
}
```
  - 응답: `201 Created` + `{ "agent": { "name": string, "status": "Active", "card": object } }`
  - 오류: `400`(스키마 오류), `401/403`(권한), `409`(중복), `502`(검증 서비스 문제)

## 데이터 저장
- 최초 실행 시 `data/agents.json`이 없으면 기본 시드가 생성됩니다.
- 신규 등록 시 `{ card, status: "Active" }` 형태로 추가 저장됩니다.

## 개발 팁
- 프론트에서 초기 목록은 `GET /api/agents`로 로드됩니다.
- 정적 서브(serve.py)만 사용하면 `/api/*` 호출은 실패하므로 등록/목록 기능 테스트에는 `server.js`를 사용하세요.

