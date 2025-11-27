from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    REDIS_URL: str = "redis://localhost:6379/0"
    TENANT_REDIS_URL: str = "redis://localhost:6379/1"

    class Config:
        env_file = ".env"


settings = Settings()
