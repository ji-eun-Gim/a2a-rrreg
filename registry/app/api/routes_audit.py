from flask import Blueprint, request, jsonify
from ..core.auditing import read_audit_events

bp = Blueprint("audit", __name__)


# 감사 로그 조회 (Redis Streams XRANGE)
@bp.get("/audit")
def audit_read():
    agent_id = request.args.get("agent_id")
    event = request.args.get("event")
    actor = request.args.get("actor")
    from_ts = request.args.get("from")
    to_ts = request.args.get("to")
    try:
        limit = int(request.args.get("limit", 50))
    except ValueError:
        limit = 50
    items = read_audit_events(agent_id=agent_id, event=event, actor=actor, from_ts=from_ts, to_ts=to_ts, limit=limit)
    return jsonify({"items": items}), 200
