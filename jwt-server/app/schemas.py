# 요청/응답 구조 정의
from pydantic import BaseModel # Pydantic은 데이터 유효성 검사를 위한 라이브러리

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: str | None = None

class User(BaseModel):
    email: str

class UserInDB(User):
    hashed_password: str