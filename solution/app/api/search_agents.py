from flask import jsonify, request

from . import api_bp
from ..core import repo

# Reasonable defaults for pagination
DEFAULT_LIMIT = 20
MAX_LIMIT = 200


@api_bp.get('/agents/search')
def search_agents():
    """에이전트 검색 API (solution) - status 기반 필터만 지원."""
    status = request.args.get('status')

    # Pagination with validation
    try:
        limit = int(request.args.get('limit', DEFAULT_LIMIT))
        offset = int(request.args.get('offset', 0))
    except (TypeError, ValueError):
        return jsonify({"error": "invalid query parameter", "message": "limit/offset must be integers"}), 400
    if limit < 1 or limit > MAX_LIMIT or offset < 0:
        return jsonify({"error": "invalid pagination", "message": f"1 <= limit <= {MAX_LIMIT}, offset >= 0"}), 400

    status_lower = status.lower() if isinstance(status, str) and status.strip() else None

    agents = repo.load_agents()
    filtered: list[dict] = []
    for agent in agents:
        if not isinstance(agent, dict):
            continue
        if status_lower:
            a_status = agent.get('status')
            if not isinstance(a_status, str) or a_status.lower() != status_lower:
                continue
        filtered.append(agent)

    total = len(filtered)
    slice_start = min(offset, total)
    slice_end = min(slice_start + limit, total)
    items = filtered[slice_start:slice_end]
    return jsonify({
        "items": items,
        "total": total,
        "limit": limit,
        "offset": slice_start,
    })
