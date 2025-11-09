from flask import Flask, jsonify, request
from urllib.parse import urlparse
from .core.redis_client import get_redis
from .core.security import auth_init, require_auth
from .core.auditing import init_auditing, audit_event
from .core.log_v3 import init_log_v3, log_event_v3
from .core.rate_limit import init_rate_limiter
import os
import threading
import json as _json

try:
    import requests as _req  # lightweight use for access-log forwarding
except Exception:  # pragma: no cover
    _req = None


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, static_folder="ui/static", static_url_path="/static")
    app.config.update(
        REDIS_URL=os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
        REGISTRY_API_TOKEN=os.environ.get("REGISTRY_API_TOKEN", "changeme"),
        # Optional: forward v3 logs in real time to an external endpoint
        LOG_FORWARD_URL=os.environ.get("LOG_FORWARD_URL"),
        LOG_FORWARD_TOKEN=os.environ.get("LOG_FORWARD_TOKEN"),
        LOG_FORWARD_OPS=os.environ.get("LOG_FORWARD_OPS"),  # e.g. "create,update"
        # Access-log forwarding toggle (default off)
        ACCESS_FORWARD_ENABLED=os.environ.get("ACCESS_FORWARD_ENABLED", "0"),
        JSON_SORT_KEYS=False,
        JSON_AS_ASCII=False,
        RATELIMIT_DEFAULT="120 per minute",
        TESTING=False,
    )
    if test_config:
        app.config.update(test_config)

    # Flask 2.3+ JSON provider 설정: 한글 그대로 출력
    try:
        app.json.ensure_ascii = False
        app.json.sort_keys = False
    except Exception:
        pass

    # Redis, 감사 로깅, 레이트 리밋 초기화
    get_redis(app)  # binds client to app.extensions['redis']
    init_auditing(app)
    init_log_v3(app)
    init_rate_limiter(app)
    auth_init(app)

    # 블루프린트 로드(앱 초기화 후 가져오기)
    from .api.routes_agents import bp as agents_bp
    from .api.routes_audit import bp as audit_bp
    from .api.routes_logs import bp as logs_bp

    app.register_blueprint(agents_bp, url_prefix="/v1")
    app.register_blueprint(audit_bp, url_prefix="/v1")
    app.register_blueprint(logs_bp, url_prefix="/v1")

    # Real-time log forwarder (optional)
    try:
        from .api.log_forwarder import init_log_forwarder

        init_log_forwarder(app)
    except Exception:
        # Forwarder is optional; ignore initialization errors to not block app startup
        pass

    # 헬스체크 엔드포인트
    @app.get("/healthz")
    def healthz():
        r = get_redis(app)
        try:
            r.ping()
            redis_status = "ok"
        except Exception:
            redis_status = "down"
        return jsonify({"status": "ok", "redis": redis_status})

    # 루트 경로: 정적 UI index 서빙
    @app.get("/")
    def index():
        return app.send_static_file("index.html")

    # 호환용: 외부 로더가 /agents 에서 카드 배열을 기대
    @app.get("/agents")
    def list_agents_flat():
        from .core.storage import search_agents
        from .core.redis_client import get_redis as _getr

        q = request.args.get("q")
        namespace = request.args.get("namespace")
        status = request.args.get("status") or "active"
        tag = request.args.get("tag")
        items, _total = search_agents(q=q, namespace=namespace, tag=tag, status=status, limit=1000, offset=0)
        out = []
        r = _getr()
        for it in items:
            card = it.get("card") or {}
            obj = {
                "name": card.get("name"),
                "description": card.get("description"),
                "version": card.get("version") or it.get("version"),
                "protocolVersion": card.get("protocolVersion"),
                "url": card.get("url"),
                "skills": card.get("skills"),
                "capabilities": card.get("capabilities"),
                "defaultInputModes": card.get("defaultInputModes"),
                "defaultOutputModes": card.get("defaultOutputModes"),
                "preferredTransport": card.get("preferredTransport"),
                "provider": card.get("provider"),
                "documentationUrl": card.get("documentationUrl"),
                "iconUrl": card.get("iconUrl"),
                "additionalInterfaces": card.get("additionalInterfaces"),
                "security": card.get("security"),
                "securitySchemes": card.get("securitySchemes"),
                "signatures": card.get("signatures"),
                "supportsAuthenticatedExtendedCard": card.get("supportsAuthenticatedExtendedCard"),
                "id": it.get("id"),
                "owner": card.get("owner") or "root",
                "created_at": None,
                "last_heartbeat": None,
            }
            try:
                h = r.hgetall(f"agent:{it.get('id')}")
                obj["created_at"] = h.get("created_at")
                obj["last_heartbeat"] = h.get("last_heartbeat") or h.get("updated_at")
                if h.get("owner"):
                    obj["owner"] = h.get("owner")
            except Exception:
                pass
            out.append(obj)
        # v3 로그: /agents 목록 조회 기록
        try:
            # 우선순위: X-Agent-URL > X-Agent-Host > X-Forwarded-For > REMOTE_ADDR (포트는 제외)
            actor_url = request.headers.get("X-Agent-URL")
            agent_host = request.headers.get("X-Agent-Host")
            actor_sub = None
            if actor_url:
                try:
                    u = urlparse(actor_url)
                    actor_sub = u.hostname or actor_url
                except Exception:
                    actor_sub = actor_url
            if not actor_sub and agent_host:
                actor_sub = agent_host
            if not actor_sub:
                xf = request.headers.get("X-Forwarded-For")
                ip = xf.split(",")[0].strip() if xf else request.remote_addr
                actor_sub = ip
            actor_tenant = namespace or "default"
            log_event_v3(
                op="read",
                phase="afterResolveRespond",
                severity="INFO",
                req_id=request.headers.get("X-Request-Id", ""),
                actor_sub=actor_sub,
                actor_tenant=actor_tenant,
                http_status=200,
                data={
                    "read": {
                        "query_name": "agents_flat",
                        "lookup_source": "db"
                    }
                },
            )
        except Exception:
            pass
        return jsonify(out), 200

    # 구조화 로그: 각 요청 처리 후 출력(JSON)
    @app.after_request
    def after(resp):
        try:
            actor = request.environ.get("actor", "anonymous")
            log = {
                "method": request.method,
                "path": request.path,
                "status": resp.status_code,
                "actor": actor,
                "ip": request.headers.get("X-Forwarded-For", request.remote_addr),
                "ua": request.headers.get("User-Agent", ""),
            }
            print(_json.dumps(log), flush=True)
            # Optional: forward structured access logs to external sink
            # Uses the same LOG_FORWARD_URL as v3 forwarder for convenience.
            # Forward structured access logs only when explicitly enabled
            forward_enabled = str(app.config.get("ACCESS_FORWARD_ENABLED", "0")).lower() in {"1", "true", "yes"}
            url = app.config.get("LOG_FORWARD_URL") if forward_enabled else None
            if url and _req is not None:
                def _send(body: dict):
                    try:
                        _req.post(
                            url,
                            data=_json.dumps({"type": "access", **body}, ensure_ascii=False).encode("utf-8"),
                            headers={"Content-Type": "application/json; charset=utf-8", "X-Log-Type": "access"},
                            timeout=1.0,
                        )
                    except Exception:
                        pass

                threading.Thread(target=_send, args=(log,), daemon=True).start()
        except Exception:
            pass
        return resp

    # 전역 에러 핸들러: JSON으로 500 응답
    @app.errorhandler(Exception)
    def handle_exception(e):
        try:
            from werkzeug.exceptions import HTTPException
            import json as _json

            if isinstance(e, HTTPException):
                return jsonify({"error": e.name, "detail": e.description}), e.code
            # 일반 예외는 500으로 처리
            return jsonify({"error": "internal server error", "detail": str(e)}), 500
        except Exception:
            return ("", 500)

    return app
