# A2A Agent Card Registry (에이전트 카드 레지스트리)

Flask + Redis 기반의 에이전트 카드 CRUD와 감사 로그(Audit Trail)를 지원하는 레지스트리 서버입니다. 간단한 웹 UI를 포함합니다.

## 빠른 시작(Quickstart)

- Docker 실행: `docker-compose up -d` 후 http://localhost:8000 접속
- 로컬 개발:
  - `python -m venv .venv && source .venv/bin/activate`
  - `pip install -e .[dev]`
  - Redis 서버 실행(예: `docker run -p 6379:6379 redis:7-alpine`)
  - 환경변수 설정:
    - `export REDIS_URL=redis://localhost:6379/0`
  - 서버 실행: `flask --app app:create_app run -p 8000`

## 엔드포인트(REST API)

- POST `/v1/agents:validate` — 검증만 수행(저장 없음)
- POST `/v1/agents` — 생성(헤더에 Authorization: Bearer 필요)
- GET `/v1/agents/{id}` — 단건 조회(READ 이벤트를 감사 스트림에 기록)
- GET `/v1/agents` — 검색 `q, namespace, tag, status, limit, offset`
- PATCH `/v1/agents/{id}` — 상태 변경 또는 카드 JSON 갱신(인증 필요)
- DELETE `/v1/agents/{id}` — 기본은 retire 표시, `?force=true` 시 완전 삭제(인증 필요)
- POST `/v1/agents:import` — URL로 가져와 검증/저장(인증 필요)
- GET `/v1/audit` — 감사 로그 조회 `agent_id, event, actor, from, to, limit`
- GET `/healthz` — 헬스체크 `{status:"ok", redis:"ok|down"}`

## 상태 코드 정책

아래 표는 A2A Agent Card 등록/조회/삭제 시 권장 상태 코드를 정의합니다. 구현도 이에 맞추어 조정되었습니다.

등록(POST `/v1/agents`)
- 401 Unauthorized: Authorization 헤더 없음/형식 오류/만료 등 인증 실패
- 403 Forbidden: 정책상 금지(URL 블랙리스트 등) 또는 권한 부족
- 400 Bad Request: JSON 파싱 오류
- 422 Unprocessable Entity: 스키마/비즈니스 규칙 위반(필수 필드 누락, 타입 불일치 등)
- 409 Conflict: 이름/URL 중복
- 201 Created: 생성 성공 (본문 포함)

조회(GET `/v1/agents/{id}`, `/v1/agents`)
- 400 Bad Request: 쿼리 파라미터 오류(limit/offset 형식·범위, 잘못된 조건 헤더 등)
- 403 Forbidden: 비정상적으로 광범위한 검색 패턴 차단(`q=*` 등)
- 404 Not Found: 리소스 없음
- 304 Not Modified: If-None-Match와 현재 ETag 일치
- 200 OK: 조회 성공 (단건/목록)

삭제(DELETE `/v1/agents/{id}`)
- 401 Unauthorized: 인증 실패
- 403 Forbidden: 권한 부족/다른 테넌트 자원
- 404 Not Found: 리소스 없음
- 412 Precondition Failed: If-Match 제공 시 ETag 불일치
- 200 OK: retire 처리(소프트 삭제)
- 204 No Content: 완전 삭제(`?force=true`)

비고
- 422는 문법적으로는 유효하나 스키마·비즈니스 규칙을 만족하지 못한 경우에 사용합니다.
- GET 단건 응답에 ETag 헤더가 포함되며, If-None-Match 일치 시 304로 본문이 생략됩니다.
- DELETE는 If-Match가 제공된 경우에만 전제 조건 검사를 수행합니다(제공 없이도 동작).

## 인증/보안

- 기본 토큰 인증(Bearer) 기반으로 보호되는 엔드포인트: 생성/수정/삭제/가져오기(import)
- 테스트/샘플 환경에서는 단건 조회/목록 조회는 공개되어 있습니다.

## 레이트 리밋(Rate Limit)

- 기본 IP당 분당 120 요청(`flask-limiter` + Redis 백엔드)

## 테스트

- `pytest -q` 실행. 테스트 모드에서는 내부 메모리 Redis 스텁(SimpleFakeRedis) 사용으로 외부 Redis 불필요

## 린트/포맷

- `ruff . && black .`

## cURL 예제

검증(validate):

```
curl -s http://localhost:8000/v1/agents:validate -H 'Content-Type: application/json' -d '{"name":"A","version":"1.0.0","protocolVersion":"1","url":"https://example.com","skills":[{"id":"s1","name":"s","description":"d"}]}'
```

생성(create):

```
curl -s -X POST http://localhost:8000/v1/agents -H 'Content-Type: application/json' -H 'Idempotency-Key: 1111-2222' -d '{"name":"A","version":"1.0.0","protocolVersion":"1","url":"https://example.com","skills":[{"id":"s1","name":"s","description":"d"}]}'
```

조회(read):

```
curl -s http://localhost:8000/v1/agents/<id>
```

수정(update):

```
curl -s -X PATCH http://localhost:8000/v1/agents/<id> -H 'Content-Type: application/json' -d '{"card":{"status":"active","name":"A2"}}'
```

삭제/폐기(delete/retire):

```
curl -s -X DELETE http://localhost:8000/v1/agents/<id>
```

가져오기(import):

```
curl -s -X POST http://localhost:8000/v1/agents:import -H 'Content-Type: application/json' -d '{"url":"https://example.com/.well-known/agent-card.json"}'
```

감사 로그(audit):

```
curl -s http://localhost:8000/v1/audit?agent_id=<id>
```

## Docker

`docker-compose up -d`로 Redis(AOF)와 애플리케이션이 함께 기동되며, 앱은 `:8000`에서 대기합니다.

## 참고 사항

- JSON Schema 검증은 에러 경로(pointer)와 메시지, 권장 필드에 대한 경고를 제공합니다.
- 감사 스트림(audit:events)에 CREATE/READ/UPDATE/DELETE가 IP/actor/변경 diff와 함께 기록됩니다.
- 검색은 Redis Set/ZSet과 간단한 필터 조합으로 구현되어 1만 건, 50 RPS 수준에서 충분한 성능을 제공합니다.
