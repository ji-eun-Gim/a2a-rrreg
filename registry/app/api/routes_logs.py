from flask import Blueprint, request, jsonify, Response, current_app
from ..core.log_v3 import read_events_v3, format_event_from_fields
from ..core.redis_client import get_redis
import json

bp = Blueprint("logs", __name__)


@bp.get("/logs")
def logs_read():
    op = request.args.get("op")
    actor_sub = request.args.get("actor_sub")
    actor_tenant = request.args.get("actor_tenant")
    target_id = request.args.get("target_id")
    try:
        limit = int(request.args.get("limit", 50))
    except ValueError:
        limit = 50
    items = read_events_v3(op=op, actor_sub=actor_sub, actor_tenant=actor_tenant, target_id=target_id, limit=limit)
    return jsonify({"items": items}), 200


@bp.get("/logs:stream")
def logs_stream():
    # Server-Sent Events for real-time notifications
    ops = request.args.get("ops")
    allow_ops = None
    if ops:
        allow_ops = set([o.strip() for o in ops.split(",") if o.strip()])

    def generate(last_id: str = "$"):
        r = get_redis()
        stream = current_app.config.get("LOG_V3_STREAM", "log:v3")
        # initial heartbeat
        yield ":ok\n\n"
        while True:
            try:
                results = r.xread({stream: last_id}, block=15000, count=50)
            except Exception:
                results = []
            if not results:
                # periodic heartbeat to keep connection alive
                yield ":keepalive\n\n"
                continue
            _, entries = results[0]
            for _id, fields in entries:
                last_id = _id
                f = {k: v for k, v in fields.items()}
                ev = format_event_from_fields(f)
                if allow_ops and ev.get("op") not in allow_ops:
                    continue
                yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"

    return Response(generate(), mimetype="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no"
    })
