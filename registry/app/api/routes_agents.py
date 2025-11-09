from flask import Blueprint, current_app, jsonify, request, abort
from werkzeug.exceptions import BadRequest
from urllib.parse import urlparse
from ..core.redis_client import get_redis
from ..core.validate import validate_agent_card
from ..core.security import require_auth
from ..core.storage import (
    create_agent,
    get_agent,
    search_agents,
    update_agent,
    retire_or_delete_agent,
    import_agent_from_url,
)
from ..core.auditing import audit_event
from ..core.log_v3 import log_event_v3
from flask_limiter.util import get_remote_address
from datetime import datetime, timezone
from ..core.blacklist import is_url_blacklisted
from ..core.etag import compute_etag

bp = Blueprint("agents", __name__)


# (검증만) 카드 유효성 검사
@bp.post("/agents:validate")
def agents_validate():
    data = request.get_json(silent=True) or {}
    valid, errors, warnings = validate_agent_card(data)
    return jsonify({"valid": valid, "errors": errors, "warnings": warnings}), 200


# 에이전트 카드 생성
@bp.post("/agents")
@require_auth
def agents_create():
    # JSON 파싱 단계 구분: 문법 오류는 400, 스키마 검증 실패는 422로 처리
    try:
        card = request.get_json(silent=False)  # BadRequest 발생 가능
        if card is None:
            card = {}
    except BadRequest as e:
        # v3 로그 (create 실패 - JSON 문법 오류)
        try:
            actor = request.environ.get("actor", "unknown")
            log_event_v3(
                op="create",
                phase="beforeCreateValidationFail",
                severity="ERROR",
                req_id=request.headers.get("Idempotency-Key", "") or request.headers.get("X-Request-Id", ""),
                actor_sub=actor or "unknown",
                actor_tenant="default",
                http_status=400,
                error_code="JSON_PARSE_ERROR",
                error_msg=str(e.description) if hasattr(e, "description") else str(e),
                data={"create": {}},
            )
        except Exception:
            pass
        return jsonify({"error": "invalid JSON"}), 400

    valid, errors, warnings = validate_agent_card(card)
    if not valid:
        # v3 로그 (create 실패 - 스키마 위반)
        try:
            actor = request.environ.get("actor", "unknown")
            tenant = card.get("namespace") or "default"
            log_event_v3(
                op="create",
                phase="beforeCreateValidationFail",
                severity="ERROR",
                req_id=request.headers.get("Idempotency-Key", "") or request.headers.get("X-Request-Id", ""),
                actor_sub=actor or "unknown",
                actor_tenant=tenant,
                http_status=422,
                error_code="SCHEMA_VIOLATION",
                error_msg="schema validation failed",
                data={"create": {}},
            )
        except Exception:
            pass
        return jsonify({"valid": False, "errors": errors}), 422

    # 3) 악성 URL 블랙리스트 검사 → 403 Forbidden
    try:
        card_url = (card or {}).get("url")
        if isinstance(card_url, str) and card_url.strip():
            blocked, meta = is_url_blacklisted(card_url)
            if blocked:
                try:
                    actor = request.environ.get("actor", "unknown")
                    tenant = card.get("namespace") or "default"
                    log_event_v3(
                        op="create",
                        phase="beforeCreateValidationFail",
                        severity="ERROR",
                        req_id=request.headers.get("Idempotency-Key", "") or request.headers.get("X-Request-Id", ""),
                        actor_sub=actor or "unknown",
                        actor_tenant=tenant,
                        http_status=403,
                        error_code="MALICIOUS_URL",
                        error_msg=f"blocked by blacklist: {meta.get('reason','unknown')}",
                        data={"create": {"url": card_url}},
                    )
                except Exception:
                    pass
                return jsonify({"error": "해당 URL은 보안 정책에 의해 허용되지 않습니다."}), 403
    except Exception:
        pass

    # 4) 동일 name 또는 동일 url 중복 체크 → 409 Conflict
    try:
        name = (card or {}).get("name")
        url = (card or {}).get("url")
        if isinstance(name, str) and name.strip() and isinstance(url, str) and url.strip():
            items, _ = search_agents(q=None, namespace=None, tag=None, status=None, limit=100000, offset=0)
            conflict_field = None
            conflict_id = None
            for it in items:
                c = it.get("card") or {}
                if c.get("name") == name:
                    conflict_field = "name"
                    conflict_id = it.get("id")
                    break
                if c.get("url") == url:
                    conflict_field = "url"
                    conflict_id = it.get("id")
                    break
            if conflict_field:
                # v3 로그 (duplicate name or url)
                try:
                    actor = request.environ.get("actor", "unknown")
                    tenant = card.get("namespace") or "default"
                    log_event_v3(
                        op="create",
                        phase="beforeCreateValidationFail",
                        severity="ERROR",
                        req_id=request.headers.get("Idempotency-Key", "") or request.headers.get("X-Request-Id", ""),
                        actor_sub=actor or "unknown",
                        actor_tenant=tenant,
                        http_status=409,
                        error_code="DUPLICATE_NAME_OR_URL",
                        error_msg="duplicate name or url",
                        data={"create": {"target_id": conflict_id, "conflict_field": conflict_field}},
                    )
                except Exception:
                    pass
                return jsonify({"error": "동일한 이름 또는 url이 존재합니다."}), 409
    except Exception:
        # 중복 검사에서 예외가 발생해도 생성 전체를 막지는 않음
        pass
    idem = request.headers.get("Idempotency-Key")
    actor = request.environ.get("actor", "unknown")
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    result = create_agent(card, idem, actor=actor, ip=ip)
    # v3 로그 (create)
    try:
        tenant = card.get("namespace") or result.get("namespace") or "default"
        log_event_v3(
            op="create",
            phase="afterCreateRespond",
            severity="INFO",
            req_id=idem or request.headers.get("X-Request-Id", ""),
            actor_sub=actor or "unknown",
            actor_tenant=tenant,
            http_status=201,
            data={
                "create": {
                    "target_id": result["id"],
                    "target_version": result.get("version", "")
                }
            },
        )
    except Exception:
        pass
    return (
        jsonify({
            "id": result["id"],
            "status": result["status"],
            "namespace": result.get("namespace"),
            "version": result.get("version"),
            "lint": warnings,
            "next": {"publish": f"PATCH /v1/agents/{result['id']}"},
        }),
        201,
    )


# 에이전트 카드 단건 조회 (READ 감사 로그 기록)
@bp.get("/agents/<agent_id>")
def agents_read(agent_id: str):
    actor = request.environ.get("actor", "anonymous")
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    agent = get_agent(agent_id)
    if not agent:
        abort(404)
    # ETag/If-None-Match handling
    try:
        current_etag = compute_etag(agent)
        inm = request.headers.get("If-None-Match")
        if inm and inm.strip() == current_etag:
            return ("", 304, {"ETag": current_etag})
    except Exception:
        current_etag = None
    # 조회수 증가는 비활성화 (로그만 기록)
    audit_event("READ", agent_id=agent_id, namespace=agent.get("namespace"), actor=actor, ip=ip, status_code=200)
    # v3 로그 (read)
    try:
        # actor_sub: 우선 X-Agent-URL 또는 X-Agent-Host, 없으면 IP (포트 제외)
        actor_url = request.headers.get("X-Agent-URL")
        agent_host = request.headers.get("X-Agent-Host")
        actor_sub = None
        if actor_url:
            try:
                from urllib.parse import urlparse as _urlparse
                u = _urlparse(actor_url)
                actor_sub = u.hostname or actor_url
            except Exception:
                actor_sub = actor_url
        if not actor_sub and agent_host:
            actor_sub = agent_host
        if not actor_sub:
            xf = request.headers.get("X-Forwarded-For")
            ip_only = xf.split(",")[0].strip() if xf else request.remote_addr
            actor_sub = ip_only
        log_event_v3(
            op="read",
            phase="afterResolveRespond",
            severity="INFO",
            req_id=request.headers.get("X-Request-Id", ""),
            actor_sub=actor_sub,
            actor_tenant=agent.get("namespace") or "default",
            http_status=200,
            data={
                "read": {
                    "lookup_source": "db",
                    "selected_id": agent.get("id"),
                    "selected_version": agent.get("version", "")
                }
            },
        )
    except Exception:
        pass
    resp = jsonify(agent)
    if current_etag:
        resp.headers["ETag"] = current_etag
    return resp, 200


# 에이전트 카드 검색 (간단 필터 + 문자열 포함 검색)
@bp.get("/agents")
def agents_search():
    q = request.args.get("q")
    namespace = request.args.get("namespace")
    tag = request.args.get("tag")
    status = request.args.get("status")
    # Validate query parameters: limit/offset must be numeric and non-negative
    try:
        limit = int(request.args.get("limit", 20))
        offset = int(request.args.get("offset", 0))
    except ValueError:
        return jsonify({"error": "invalid query parameter: limit/offset must be integers"}), 400
    if limit < 1 or offset < 0:
        return jsonify({"error": "invalid query parameter: limit>=1 and offset>=0 required"}), 400
    # Unsupported sort/filter values
    sort = request.args.get("sort")
    if sort:
        return jsonify({"error": "unsupported sort parameter"}), 400
    # Overly broad search pattern policy: block wildcard-only dumps
    if isinstance(q, str) and q.strip() == "*":
        return jsonify({"error": "forbidden search pattern"}), 403
    items, total = search_agents(q=q, namespace=namespace, tag=tag, status=status, limit=limit, offset=offset)
    return jsonify({"items": items, "total": total, "limit": limit, "offset": offset}), 200


# 카탈로그 형식 목록(요청 포맷에 맞춰 평탄화)
@bp.get("/agents:catalog")
def agents_catalog():
    q = request.args.get("q")
    namespace = request.args.get("namespace")
    tag = request.args.get("tag")
    status = request.args.get("status") or "active"
    items, total = search_agents(q=q, namespace=namespace, tag=tag, status=status, limit=1000, offset=0)
    out = []
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
            "owner": it.get("owner") or card.get("owner") or "root",
            "created_at": None,
            "last_heartbeat": None,
        }
        try:
            r = get_redis()
            h = r.hgetall(f"agent:{it.get('id')}")
            obj["created_at"] = h.get("created_at")
            obj["last_heartbeat"] = h.get("last_heartbeat") or h.get("updated_at")
        except Exception:
            pass
        out.append(obj)
    return jsonify(out), 200


# 에이전트 하트비트 갱신
@bp.post("/agents/<agent_id>:heartbeat")
def agents_heartbeat(agent_id: str):
    try:
        r = get_redis()
        key = f"agent:{agent_id}"
        if not r.exists(key):
            return jsonify({"error": "not found"}), 404
        now = datetime.now(timezone.utc).isoformat()
        r.hset(key, mapping={"last_heartbeat": now})
        return jsonify({"ok": True, "id": agent_id, "last_heartbeat": now}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# 카드/상태 부분 수정 (버전 변경 시 semver 재지정)
@bp.patch("/agents/<agent_id>")
@require_auth
def agents_update(agent_id: str):
    payload = request.get_json(silent=True) or {}
    actor = request.environ.get("actor", "unknown")
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    # 기존 버전 확보(로그용)
    before = get_agent(agent_id)
    ok, result_or_error = update_agent(agent_id, payload, actor=actor, ip=ip)
    if not ok:
        # v3 로그 (update 실패 - 스키마 위반으로 간주, 422)
        try:
            log_event_v3(
                op="update",
                phase="afterUpdateRespond",
                severity="ERROR",
                req_id=request.headers.get("X-Request-Id", ""),
                actor_sub=actor or "unknown",
                actor_tenant=(before or {}).get("namespace") or "default",
                http_status=422,
                error_code="SCHEMA_VIOLATION",
                error_msg="schema validation failed",
                data={
                    "update": {
                        "target_id": agent_id,
                        "from_version": (before or {}).get("version", "")
                    }
                },
            )
        except Exception:
            pass
        # result_or_error가 검증 오류 상세를 담고 있으면 그대로 반환
        status_body = result_or_error if isinstance(result_or_error, dict) else {"error": result_or_error}
        return jsonify(status_body), 422
    # v3 로그 (update 성공 / 상태 변경에 따른 deprecate 분기)
    try:
        after = result_or_error
        next_op = "update"
        try:
            if (before or {}).get("status") != after.get("status") and after.get("status") == "deprecated":
                next_op = "deprecate"
        except Exception:
            pass
        log_event_v3(
            op=next_op,
            phase="afterUpdateRespond",
            severity="INFO",
            req_id=request.headers.get("X-Request-Id", ""),
            actor_sub=actor or "unknown",
            actor_tenant=result_or_error.get("namespace") or "default",
            http_status=200,
            data={
                next_op: {
                    "target_id": agent_id,
                    "from_version": (before or {}).get("version", ""),
                    "to_version": result_or_error.get("version", "")
                }
            },
        )
    except Exception:
        pass
    return jsonify(result_or_error), 200


# 삭제/폐기: 기본은 retired 마킹, force=true 시 완전 삭제
@bp.delete("/agents/<agent_id>")
@require_auth
def agents_delete(agent_id: str):
    force = request.args.get("force") == "true"
    actor = request.environ.get("actor", "unknown")
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    before = get_agent(agent_id)
    # Optional precondition check with If-Match
    try:
        if before is None:
            return jsonify({"error": "not found"}), 404
        current_etag = compute_etag(before)
        if_match = request.headers.get("If-Match")
        if if_match and if_match.strip() != current_etag:
            return jsonify({"error": "precondition failed"}), 412
    except Exception:
        pass
    result, status_code = retire_or_delete_agent(agent_id, force=force, actor=actor, ip=ip)
    if status_code == 204:
        # v3 로그 (force 삭제: revoke로 기록)
        try:
            log_event_v3(
                op="revoke",
                phase="afterDeleteRespond",
                severity="INFO",
                req_id=request.headers.get("X-Request-Id", ""),
                actor_sub=actor or "unknown",
                actor_tenant=(before or {}).get("namespace") or "default",
                http_status=204,
                data={
                    "revoke": {
                        "target_id": agent_id
                    }
                },
            )
        except Exception:
            pass
        return ("", 204)
    # v3 로그 (retire)
    try:
        log_event_v3(
            op="retire",
            phase="afterDeleteRespond",
            severity="INFO" if status_code == 200 else "ERROR",
            req_id=request.headers.get("X-Request-Id", ""),
            actor_sub=actor or "unknown",
            actor_tenant=(before or {}).get("namespace") or "default",
            http_status=status_code,
            data={
                "retire": {
                    "target_id": agent_id,
                    "tombstone": True
                }
            },
        )
    except Exception:
        pass
    return jsonify(result), status_code


# 외부 URL에서 카드 가져오기(import)
@bp.post("/agents:import")
@require_auth
def agents_import():
    body = request.get_json(silent=True) or {}
    url = body.get("url")
    verify = body.get("verify", {})
    if not url:
        return jsonify({"error": "url required"}), 400
    actor = request.environ.get("actor", "unknown")
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    ok, data = import_agent_from_url(url, verify=verify, actor=actor, ip=ip)
    if not ok:
        return jsonify({"error": data}), 400
    return jsonify(data), 201
