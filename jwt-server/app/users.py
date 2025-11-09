from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from .auth import verify_password, hash_password, create_access_token, decode_access_token
from .schemas import User, UserInDB, Token

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# 임시 유저 DB
fake_users_db = {
    "user@example.com": {
        "email": "user@example.com",
        "hashed_password": hash_password("password123"),
    },
    "admin@example.com": {
        "email": "admin@example.com",
        "hashed_password": hash_password("admin123"),
    }
}

def get_user(email: str):
    user = fake_users_db.get(email)
    if user:
        return UserInDB(**user)

# FastAPI에서 로그인용 토큰을 발급하는 엔드포인트
@router.post("/token", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = get_user(form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invailid credentials")
    
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

# 토큰 속에서 이메일로 사용자 정보를 찾아 리턴하는 엔드포인트
@router.get("/users/me", response_model=User)
def read_users_me(token: str = Depends(oauth2_scheme)):
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token")
    
    email: str = payload.get("sub")
    user = get_user(email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found")
    
    return user
