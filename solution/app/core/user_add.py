"""JWT 서버 user DB에서 사용자 목록(name, title, email)을 가져오는 헬퍼."""

from __future__ import annotations

import os
import redis
import json
from typing import List, Dict, Any

# 기본 후보: 컨테이너 환경을 고려해 jwt-server 호스트 우선
_USER_REDIS_URLS = [
    os.getenv("JWT_REDIS_URL"),
    "redis://jwt-server:6380/0",
    "redis://localhost:6380/0",
    os.getenv("REDIS_URL"),
]


def _pick_redis_url() -> str:
    for url in _USER_REDIS_URLS:
        if url:
            return url
    return "redis://localhost:6379/0"


def redis_client():
    return redis.Redis.from_url(_pick_redis_url(), decode_responses=True)


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


def list_users() -> List[Dict[str, Any]]:
    """Fetch user hashes stored by the JWT server under keys like `user:<email>`."""
    client = redis_client()
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
            }
        )

    return users


if __name__ == "__main__":
    try:
        url = _pick_redis_url()
        print(f"[INFO] using redis url: {url}")
        found = list_users()
        print(f"[INFO] found {len(found)} user(s)")
        for item in found:
            print(json.dumps(item, ensure_ascii=False))
    except Exception as e:
        print(f"[ERR] failed to list users: {e}")
