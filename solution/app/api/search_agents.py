from flask import jsonify, request, g

from . import api_bp
from ..core import repo
from ..core.auth import require_jwt
from ..core.logging import append_log

# Reasonable defaults for pagination
DEFAULT_LIMIT = 20
MAX_LIMIT = 200


@api_bp.get('/agents/search')
def search_agents():
    """에이전트 검색 API (solution) - tenant 제한 + Active 상태만 노출."""
    auth_err = require_jwt()
    if auth_err:
        return auth_err

    jwt_info = getattr(g, "jwt", {}) or {}
    is_admin = jwt_info.get("role") == "admin"
    token_tenants = jwt_info.get("tenants") or []
    if not is_admin and not token_tenants:
        append_log('에이전트 조회 거부 : JWT tenant claim 없음 (403 Forbidden)', False, capture_client_ip=True)
        return jsonify({"error": "TENANT_REQUIRED", "message": "tenant claim missing in JWT"}), 403

    status_param = request.args.get('status')
    if status_param and status_param.strip().lower() != 'active':
        append_log('에이전트 조회 거부 : Active 상태만 허용 (403 Forbidden)', False, capture_client_ip=True)
        return jsonify({"error": "STATUS_FORBIDDEN", "message": "Only Active agents can be queried"}), 403

    # Pagination with validation
    try:
        limit = int(request.args.get('limit', DEFAULT_LIMIT))
        offset = int(request.args.get('offset', 0))
    except (TypeError, ValueError):
        append_log('에이전트 조회 실패 : 잘못된 pagination 파라미터 (400 Bad Request)', False, capture_client_ip=True)
        return jsonify({"error": "invalid query parameter", "message": "limit/offset must be integers"}), 400
    if limit < 1 or limit > MAX_LIMIT or offset < 0:
        append_log('에이전트 조회 실패 : pagination 범위 위반 (400 Bad Request)', False, capture_client_ip=True)
        return jsonify({"error": "invalid pagination", "message": f"1 <= limit <= {MAX_LIMIT}, offset >= 0"}), 400

    status_lower = 'active'
    allowed_tenants = {t.strip().lower() for t in token_tenants if isinstance(t, str)}

    agents = repo.load_agents()
    filtered: list[dict] = []
    for agent in agents:
        if not isinstance(agent, dict):
            continue
        if status_lower:
            a_status = agent.get('status')
            if not isinstance(a_status, str) or a_status.lower() != status_lower:
                continue
        if not is_admin:
            record_tenants = agent.get('tenants')
            if not isinstance(record_tenants, list):
                record_tenants = []
            if not any(
                isinstance(t, str) and t.strip().lower() in allowed_tenants
                for t in record_tenants
            ):
                continue
        filtered.append(agent)

    total = len(filtered)
    slice_start = min(offset, total)
    slice_end = min(slice_start + limit, total)
    items = filtered[slice_start:slice_end]
    resp = {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": slice_start,
    }
    scope = "admin" if is_admin else ",".join(sorted(allowed_tenants)) or "none"
    append_log(f"에이전트 조회 성공 (200 OK): scope={scope}, returned={len(items)}", True, capture_client_ip=True)
    return jsonify(resp)
