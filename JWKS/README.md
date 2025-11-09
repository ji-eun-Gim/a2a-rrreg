# JWS 발급 서버 (RS256)

`jws` 패키지와 RS256(RSA + SHA‑256) 알고리즘을 사용해 JSON Web Signature(JWS)를 발급하는 FastAPI 서버입니다.

## 준비 사항

- Python 3.10 이상
- 의존성 설치:

```
pip install -r requirements.txt
```

- RSA 개인키 설정(.env 사용 권장):

```
# .env에 PEM 문자열로 직접 제공(이스케이프된 줄바꿈 사용)
RS256_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\nREPLACE_WITH_YOUR_RSA_PRIVATE_KEY_BODY\n-----END PRIVATE KEY-----\n"
```

## 실행

```
uvicorn app:app --env-file .env --host 0.0.0.0 --port 8000
```

헬스 체크:

```
curl http://localhost:8000/
```

## 페이로드 서명

요청 예시:

```
curl -s -X POST http://localhost:8000/sign \
  -H "Content-Type: application/json" \
  -d '{
        "payload": {"sub": "123", "name": "Alice", "iat": 1710000000},
        "kid": "key-1"
      }'
```

응답 예시:

```
{
  "token": "<compact-jws>",
  "alg": "HS256",
  "kid": "key-1"
}
```

비고
- `kid`는 선택 값입니다. 일부 `jws` 버전은 커스텀 헤더를 지원하지 않을 수 있으므로, 미지원 시 `kid`를 생략하세요.
- 이 서버는 일반적인 JWS를 발급합니다. 만약 만료(`exp`), Not‑Before(`nbf`) 등 JWT 클레임 처리까지 필요하다면 `PyJWT` 또는 `python-jose` 사용을 고려하세요.

## 토큰 검증 예시

RS256 공개키(또는 인증서)로 검증하려면:

```python
import jws

public_key_pem = """-----BEGIN PUBLIC KEY-----
REPLACE_WITH_YOUR_RSA_PUBLIC_KEY_BODY
-----END PUBLIC KEY-----
"""
compact = "<compact-jws>"
payload = jws.verify(compact, public_key_pem, algorithms=["RS256"])  # dict 반환
print(payload)
```

## 환경 변수

- `RS256_PRIVATE_KEY` 또는 `RS256_PRIVATE_KEY_PATH`(필수 택1): RSA 개인키(PEM) 제공
- `HOST`(선택): `python app.py`로 실행 시 바인딩 호스트(기본 `0.0.0.0`)
- `PORT`(선택): `python app.py`로 실행 시 포트(기본 `8000`)
- `RELOAD`(선택): `python app.py`로 실행 시 `1`로 설정하면 자동 리로드 활성화
