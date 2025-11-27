"""Helpers to read user records from the JWT server's Redis."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List

import redis


_FALLBACK_REDIS_URLS = (
    os.environ.get("JWT_REDIS_URL"),
    os.environ.get("REDIS_URL"),
    "redis://jwt-server:6380/0",  # when jwt-server runs in docker-compose
    "redis://host.docker.internal:6381/0",  # when jwt-server runs in sibling container
    "redis://localhost:6380/0",
)


def _pick_redis_url(explicit_url: str | None = None) -> str:
    if explicit_url:
        return explicit_url
    for url in _FALLBACK_REDIS_URLS:
        if url:
            return url
    return "redis://localhost:6380/0"


def redis_client(redis_url: str | None = None) -> redis.Redis:
    """Return a Redis client configured to decode responses as strings."""
    url = _pick_redis_url(redis_url)
    return redis.Redis.from_url(url, decode_responses=True)


def _normalize_tenants(raw_value: Any) -> List[str]:
    """Convert stored tenant value (string or JSON list) to a list of strings."""
    if raw_value is None:
        return []
    if isinstance(raw_value, list):
        return [str(item) for item in raw_value if isinstance(item, str)]
    if isinstance(raw_value, str):
        try:
            parsed = json.loads(raw_value)
            if isinstance(parsed, list):
                return [str(item) for item in parsed if isinstance(item, str)]
        except json.JSONDecodeError:
            pass
        return [raw_value] if raw_value else []
    return []


def list_users(redis_url: str | None = None) -> List[Dict[str, Any]]:
    """Fetch user hashes stored by the JWT server under keys like `user:<email>`."""
    client = redis_client(redis_url)
    users: List[Dict[str, Any]] = []

    for key in client.scan_iter(match="user:*"):
        data = client.hgetall(key)
        if not data:
            continue
        users.append(
            {
                "email": data.get("email"),
                "name": data.get("name") or data.get("email"),
                "title": data.get("title") or "",
                "tenants": _normalize_tenants(data.get("tenant")),
                "hashed_password": data.get("hashed_password"),
            }
        )

    return users


if __name__ == "__main__":
    # Quick manual check: python -m app.core.user
    found = list_users()
    print(f"found {len(found)} user(s)")
    for item in found:
        print(json.dumps(item, ensure_ascii=False))
