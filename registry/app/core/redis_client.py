from __future__ import annotations
from flask import current_app
import redis


# 테스트 모드에서 사용할 간단한 인메모리 Redis 대체 구현
class SimpleFakeRedis:
    def __init__(self):
        self.kv = {}
        self.hashes = {}
        self.sets = {}
        self.zsets = {}
        self.streams = {}

    def ping(self):
        return True

    def hset(self, key, *args, **kwargs):
        # Support both hset(key, mapping={...}) and hset(key, field, value)
        h = self.hashes.setdefault(key, {})
        if args and len(args) == 2:
            field, value = args
            h[str(field)] = value
            return 1
        mapping = kwargs.get("mapping")
        if isinstance(mapping, dict):
            h.update(mapping)
            return len(mapping)
        raise TypeError("hset requires mapping= or field,value")

    def hgetall(self, key):
        return dict(self.hashes.get(key, {}))

    def sadd(self, key, *members):
        s = self.sets.setdefault(key, set())
        for m in members:
            s.add(m)

    def srem(self, key, member):
        self.sets.setdefault(key, set()).discard(member)

    def smembers(self, key):
        return set(self.sets.get(key, set()))

    def zadd(self, key, mapping):
        z = self.zsets.setdefault(key, {})
        for member, score in mapping.items():
            z[member] = score

    def get(self, key):
        v = self.kv.get(key)
        return v

    def setex(self, key, ttl, value):
        # 단순 스텁: TTL은 무시하고 값만 보관
        self.kv[key] = value

    def incr(self, key):
        self.kv[key] = str(int(self.kv.get(key, 0)) + 1)
        return int(self.kv[key])

    def delete(self, key):
        self.hashes.pop(key, None)
        self.kv.pop(key, None)

    def xadd(self, stream, fields):
        self.streams.setdefault(stream, []).append(("*", fields))

    def xrange(self, stream, min="-", max="+", count=None):
        arr = list(self.streams.get(stream, []))
        if count is not None:
            arr = arr[:count]
        return arr


def get_redis(app=None) -> redis.Redis:
    app = app or current_app
    if not hasattr(app, "extensions"):
        app.extensions = {}
    if app.extensions.get("redis") is None:
        url = app.config.get("REDIS_URL", "redis://localhost:6379/0")
        # In tests, allow injection of a FakeRedis via app.config['REDIS_CLIENT']
        client = app.config.get("REDIS_CLIENT")
        if client is None:
            if app.config.get("TESTING"):
                client = SimpleFakeRedis()
            else:
                # 실제 Redis 시도, 실패 시 인메모리로 폴백
                try:
                    client = redis.from_url(url, decode_responses=True)
                    # 연결 확인
                    client.ping()
                except Exception:
                    client = SimpleFakeRedis()
                    app.config["REDIS_FALLBACK"] = True
        app.extensions["redis"] = client
    return app.extensions["redis"]
