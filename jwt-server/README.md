# 구조 요약
- 서버 관련 코드(Dockerfile, requirements.txt, .env, app/)는 저장소 루트에 있으며, `app/` 안에 FastAPI 구현이 들어 있습니다.
- `test/` : 브라우저에서 실행하는 로그인 테스트 페이지입니다.

# 서버 실행 (개발용)
1. 저장소 루트에서 `uvicorn app.main:app --reload`로 API를 실행합니다.  
2. API는 `.env`/`app` 폴더를 읽고 Redis 연결(기본 `redis://localhost:6379/0`)에서 사용자 데이터를 조회합니다.

# Docker Compose로 실행
1. 저장소 루트에서 `docker compose up --build`를 실행하면 현재 컨텍스트(`.`)를 이용해 FastAPI와 Redis가 함께 올라갑니다.  
2. `app` 서비스는 Compose가 제공하는 `REDIS_URL=redis://redis:6379/0`을 쓰고, `docker-compose.yml`이 `./.env`를 참조합니다.  
3. `http://localhost:8000/docs`에서 `/token`/`/users/me`를 호출하거나 CURL/Postman으로 토큰을 발급받아 확인하세요.  
4. 마무리할 때는 `docker compose down`으로 컨테이너를 종료합니다.

# 로그인 테스트 페이지
1. FastAPI가 실행된 상태에서 다른 터미널로 `cd test` 후 `python -m http.server 8081` 또는 `npx serve .`로 정적 서버를 띄웁니다.  
2. `http://localhost:8081`에 접속하면 이메일/비밀번호 입력 폼이 나타나며 `/token`으로 POST 요청을 보냅니다.  
3. `admin@example.com`이면 “안녕하세요 관리자님”, 다른 계정이면 “안녕하세요 일반 사용자님” 메시지와 함께 JWT가 출력됩니다.  
4. 토큰을 `Authorization: Bearer <token>` 헤더로 `/users/me`에 전달하면 인증이 정상인지 직접 볼 수 있습니다.

# API 개요

## 1. `POST /token`
OAuth2 비밀번호 방식으로 로그인한 뒤 액세스 토큰을 반환합니다. 요청 본문은 `username`, `password` 필드를 가진 form-data 여야 합니다. 현재 `app/users.py` 에 정의된 fake DB에는 아래 계정이 등록되어 있고, 각 계정의 tenant 정보도 토큰에 같이 담깁니다.

| 이메일 | 비밀번호 | tenant |
| --- | --- | --- |
| `user2@example.com` | `password1234` | `logistics` |
| `user@example.com` | `password123` | `customer-service` |
| `admin@example.com` | `admin123` | `["logistics", "customer-service"]` |

성공하면 `access_token` 과 `token_type` 이 응답됩니다.

## 2. `GET /users/me`
`Authorization: Bearer <access_token>` 헤더로 요청하면 토큰을 디코딩해서 사용자 정보를 반환합니다.  `users.py` 에서도 보듯이 토큰의 `sub`(이메일)과 `tenant` 클레임이 fake DB의 값과 일치하지 않으면 `404 Not Found` 를 반환합니다. `tenant` 클레임은 문자열 또는 문자열 목록 모두 정규화하여 비교하므로 여러 tenant 를 가진 관리자가 토큰으로 접근할 수 있습니다.

## 상세 흐름

1. `/token` 엔드포인트로 로그인 시도.
2. fake DB 에서 사용자 확인 후 패스워드를 조회해서 비교.
3. `create_access_token` 으로 email + tenant 정보가 포함된 JWT를 발급.
4. 클라이언트가 `/users/me` 로 요청 시 토큰을 검증하고, 입력된 tenant 클레임과 fake DB의 tenant가 정확히 일치하는지 확인.
5. 조건을 만족하면 `User` 모델 형태의 사용자 데이터를 반환.
