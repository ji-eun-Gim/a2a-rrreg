from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


def init_rate_limiter(app):
    # 테스트 환경에서는 메모리 스토리지로 동작하여 외부 Redis 의존 제거
    storage_uri = (
        "memory://" if app.config.get("TESTING") else app.config.get("REDIS_URL", "redis://localhost:6379/0")
    )
    Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=[app.config.get("RATELIMIT_DEFAULT", "120 per minute")],
        storage_uri=storage_uri,
        strategy="fixed-window",
    )
