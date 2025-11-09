# ============================================================
# 📘 JWS Issuer (RS256)
# - FastAPI 기반으로 작성된 간단한 JWS 서명 서버
# - 클라이언트가 payload(JSON 데이터)를 보내면 RS256 알고리즘으로 서명된 JWS 토큰을 반환
# - RSA 개인키(PEM)를 .env 또는 환경 변수로 로드하여 사용
#   (RS256_PRIVATE_KEY 또는 RS256_PRIVATE_KEY_PATH)
# ============================================================

import os
import json
from pathlib import Path
import json
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv


# jws 모듈 임포트 시도
#  - JSON Web Signature 관련 기능을 제공
#  - 라이브러리가 없을 경우 예외 발생하지만, 서버 구동은 일단 진행하고
#    실제 요청이 들어올 때 에러를 던지도록 처리
try:
    import jws  # type: ignore
except Exception as e:  # pragma: no cover
    jws = None  # type: ignore  # 라이브러리 미존재 시 None으로 설정


# 요청(Request) 및 응답(Response) 모델 정의
class SignRequest(BaseModel):
    """
    클라이언트가 서명을 요청할 때 보내는 데이터 구조
    - payload: 실제 서명할 JSON 데이터 (dict)
    - kid: (선택) Key ID, 헤더에 포함되어 특정 키를 식별할 때 사용
    """
    payload: Dict[str, Any]
    kid: Optional[str] = None


class SignResponse(BaseModel):
    """
    서버가 서명 후 반환하는 데이터 구조
    - token: 생성된 JWS 토큰 문자열
    - alg: 사용된 알고리즘 (여기서는 RS256)
    - kid: 요청 시 포함된 Key ID (있을 경우 반환)
    """
    token: str
    alg: str
    kid: Optional[str] = None

# 알고리즘 설정 (RS256 = RSA + SHA-256)
ALG = "RS256"

# RSA 개인키(PEM) 가져오기 함수
#  - RS256_PRIVATE_KEY: PEM 문자열을 직접 환경 변수에 담아 제공
#  - RS256_PRIVATE_KEY_PATH: PEM 파일 경로를 지정하여 로드
#  - 둘 다 없으면 RuntimeError 발생
def get_private_key_pem() -> str:
    pem = os.getenv("RS256_PRIVATE_KEY")
    if pem:
        # .env에 이스케이프된 "\n"으로 들어온 경우 실제 개행으로 변환
        if "\\n" in pem and "\n" not in pem:
            pem = pem.replace("\\n", "\n")
        return pem
    path = os.getenv("RS256_PRIVATE_KEY_PATH")
    if path and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    raise RuntimeError(
        "Provide RSA private key via RS256_PRIVATE_KEY or RS256_PRIVATE_KEY_PATH"
    )


# .env 자동 로드 및 FastAPI 애플리케이션 생성
# 실행 CWD가 달라도 프로젝트 루트의 .env를 읽도록 경로 지정
load_dotenv(dotenv_path=Path(__file__).with_name(".env"))
app = FastAPI(title="JWS Issuer (RS256)", version="1.0.0")

# 루트 엔드포인트 (건강 상태 확인용)
@app.get("/")
def read_root() -> Dict[str, str]:
    """
    단순 헬스체크 엔드포인트.
    서버가 정상적으로 작동 중임을 확인하기 위해 사용.
    """
    return {"status": "ok"}


# /sign 엔드포인트: JWS 서명 기능
@app.post("/sign", response_model=SignResponse)
def sign(req: SignRequest) -> SignResponse:
    """
    클라이언트가 JSON payload를 전송하면, 해당 데이터를 RS256 알고리즘으로 서명하여
    JWS 토큰을 생성한 뒤 반환하는 엔드포인트.
    """

    # jws 모듈이 없는 경우 서버 에러 반환
    if jws is None:
        raise HTTPException(status_code=500, detail="jws library is not available")

    # RSA 개인키(PEM) 가져오기
    try:
        private_key_pem = get_private_key_pem()
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    # PEM 문자열을 RSA 개인키 객체로 변환 (pycryptodome)
    try:
        from Crypto.PublicKey import RSA  # type: ignore
        private_key_obj = RSA.import_key(private_key_pem)
    except ModuleNotFoundError:
        raise HTTPException(status_code=500, detail="Crypto backend missing. Install 'pycryptodome'.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid RSA private key: {e}")

    # JOSE 헤더 구성 (alg 필수, kid 선택)
    head: Dict[str, Any] = {"alg": ALG}
    if req.kid:
        head["kid"] = req.kid

    # 실제 서명 수행: jws.sign(head_json, payload_json, key=..., is_json=True)
    try:
        head_json = json.dumps(head, separators=(",", ":"))
        payload_json = json.dumps(req.payload, separators=(",", ":"))
        signature_b64 = jws.sign(head_json, payload_json, key=private_key_obj, is_json=True)
    except ModuleNotFoundError as exc:
        # Crypto 백엔드 미설치 등 (PyCryptodome 필요)
        raise HTTPException(
            status_code=500,
            detail="Crypto backend missing. Install 'pycryptodome'.",
        )
    except Exception as exc:
        # 기타 예외는 클라이언트 요청 문제 또는 구성 문제로 간주
        raise HTTPException(status_code=400, detail=f"Signing failed: {exc}")

    # compact JWS 조립: base64url(header).base64url(payload).base64url(signature)
    from jws import utils as jutils

    b64_head = jutils.base64url_encode(head_json)
    b64_payload = jutils.base64url_encode(payload_json)
    # sign()은 이미 base64url(signature)를 반환하므로 그대로 사용
    b64_sig = signature_b64
    compact = (b64_head + b"." + b64_payload + b"." + b64_sig).decode("ascii")

    # 결과 반환
    return SignResponse(token=compact, alg=ALG, kid=req.kid)


# ------------------------------------------------------------
# 메인 실행 부분
#  - uvicorn을 이용해 로컬 서버 구동
#  - 환경 변수로 호스트/포트/리로드 설정 가능
# ------------------------------------------------------------
if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run(
        "app:app",
        host=os.getenv("HOST", "0.0.0.0"),           # 기본: 모든 인터페이스에서 접근 허용
        port=int(os.getenv("PORT", "8000")),         # 기본 포트: 8000
        reload=bool(os.getenv("RELOAD", "0") == "1") # 코드 변경 시 자동 리로드 여부
    )
