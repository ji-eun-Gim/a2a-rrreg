# JWT Auth Server

## 요구 사항
- Python 3.10+
- `pip`

## 설치
1) 가상환경 생성 및 활성화
```
python -m venv .venv
# Windows
.venv\\Scripts\\activate
# macOS/Linux
source .venv/bin/activate
```

2) 패키지 설치
```
pip install -r requirements.txt
```

3) 환경변수 설정(`.env` 파일 생성)
```
SECRET_KEY=change-me
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```
참고: 현재 설정은 정수 분 단위를 사용합니다. 30초와 같이 소수 분(예: `0.5`)을 쓰려면 `app/config.py`의 타입을 `float`로 변경해야 합니다.

## 실행
```
uvicorn app.main:app --reload
```

## API 테스트
- 브라우저: http://127.0.0.1:8000/docs 접속 → Swagger UI 사용
- 토큰 발급: `/token` (OAuth2PasswordRequestForm: `username`, `password`)
- 발급된 `access_token`으로 Authorize → `/users/me` 호출

### 데모 계정
- 일반 사용자: `user@example.com` / `password123`
- 관리자: `admin@example.com` / `admin123`

## cURL 예시
토큰 발급:
```
curl -X POST \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=user@example.com&password=password123" \
  http://127.0.0.1:8000/token
```

토큰으로 자기 정보 조회:
```
curl -H "Authorization: Bearer <ACCESS_TOKEN>" \
  http://127.0.0.1:8000/users/me
```

## 문제 해결
- 401 Invalid token: 토큰 만료 또는 `SECRET_KEY`/`ALGORITHM` 불일치 확인
- 환경 로딩 오류: `.env` 존재/값 형식(정수 분) 확인
