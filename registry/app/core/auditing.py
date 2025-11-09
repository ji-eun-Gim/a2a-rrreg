from __future__ import annotations
from flask import current_app
from .redis_client import get_redis
from datetime import datetime
import json


AUDIT_STREAM = "audit:events"  # 감사 로그 Redis Stream 키


def init_auditing(app):
    # 현재는 설정만 보장(향후 확장 지점)
    app.config.setdefault("AUDIT_STREAM", AUDIT_STREAM)


def audit_event(event: str, agent_id: str | None, namespace: str | None, actor: str, ip: str, status_code: int, diff_json: dict | None = None):
    # 감사 이벤트를 Redis Stream에 XADD로 기록
    r = get_redis()
    payload = {
        "event": event,
        "agent_id": agent_id or "",
        "namespace": namespace or "",
        "actor": actor,
        "ip": ip,
        "status_code": str(status_code),
        "ts": datetime.utcnow().isoformat() + "Z",
    }
    if diff_json is not None:
        payload["diff_json"] = json.dumps(diff_json, ensure_ascii=False)
    r.xadd(current_app.config.get("AUDIT_STREAM", AUDIT_STREAM), payload)


def read_audit_events(agent_id: str | None, event: str | None, actor: str | None, from_ts: str | None, to_ts: str | None, limit: int = 50):
    # 필터 조건에 맞는 이벤트를 XRANGE로 조회(간단 필터)
    r = get_redis()
    stream = current_app.config.get("AUDIT_STREAM", AUDIT_STREAM)
    start = "-" if not from_ts else from_ts
    end = "+" if not to_ts else to_ts
    try:
        entries = r.xrange(stream, min=start, max=end, count=limit)
    except Exception:
        entries = []
    items = []
    for _id, fields in entries:
        f = {k: v for k, v in fields.items()}
        if agent_id and f.get("agent_id") != agent_id:
            continue
        if event and f.get("event") != event:
            continue
        if actor and f.get("actor") != actor:
            continue
        if "diff_json" in f:
            try:
                f["diff_json"] = json.loads(f["diff_json"]) if isinstance(f["diff_json"], str) else f["diff_json"]
            except Exception:
                pass
        items.append(f)
        if len(items) >= limit:
            break
    return items
