# 서버 실행 방법
```
uvicorn app.main:app --reload
```

# API 테스트
브라우저에서 http://127.0.0.1:8000/docs 접속 → Swagger UI 실행

1. /token 엔드포인트에서 로그인 시도

(일반 사용자)
- username: user@example.com
- password: password123

(관리자)
- username: admin@example.com
- password: admin123

2. 응답으로 access_token 확인

3. Authorize 버튼 클릭 → 토큰 붙여넣기 → /users/me 호출

4. 이메일 정보 반환 확인