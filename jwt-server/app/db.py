"""Redis client configuration shared across the app."""

import redis

from .config import settings


# decode_responses ensures we always work with Python strings
redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
tenant_redis_client = redis.Redis.from_url(
    settings.TENANT_REDIS_URL, decode_responses=True
)
