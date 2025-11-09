from __future__ import annotations
from functools import wraps
from flask import request, current_app, jsonify


def auth_init(app):
    # 기본 actor 초기화
    @app.before_request
    def set_actor():
        request.environ["actor"] = "anonymous"


def require_auth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        authz = request.headers.get("Authorization", "")
        scheme, _, token = authz.partition(" ")
        if scheme.lower() != "bearer" or not token:
            resp = jsonify({"error": "unauthorized"})
            resp.headers["WWW-Authenticate"] = "Bearer"
            return resp, 401
        expected = current_app.config.get("REGISTRY_API_TOKEN")
        if not expected or token != expected:
            resp = jsonify({"error": "unauthorized"})
            resp.headers["WWW-Authenticate"] = "Bearer error=\"invalid_token\""
            return resp, 401
        # 인증 성공: actor에 토큰 사용자를 기록(토큰 값은 마스킹)
        request.environ["actor"] = "token"
        return fn(*args, **kwargs)

    return wrapper
