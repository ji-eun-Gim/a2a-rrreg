from __future__ import annotations
import uuid
from datetime import datetime, timezone
from flask import current_app
from .redis_client import get_redis


LOG_V3_STREAM = "log:v3"  # 별도 로그 저장용 Redis Stream 키


def _now_iso_z() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def init_log_v3(app):
    app.config.setdefault("LOG_V3_STREAM", LOG_V3_STREAM)


def log_event_v3(
    *,
    op: str,
    phase: str,
    severity: str,
    req_id: str,
    actor_sub: str,
    actor_tenant: str,
    data: dict,
    http_status: int | None = None,
    error_code: str | None = None,
    error_msg: str | None = None,
):
    """
    최소 v3 스키마에 맞춰 이벤트를 Redis Stream에 저장.
    - 스키마 필수 필드만 구성하고, data는 oneOf 중 해당 op 블록만 포함해야 함.
    - 유효성 검사는 최소화(포맷/열거값 위주)하고 저장에 집중.
    """
    # 정규화/간단 검증
    op = str(op)
    phase = str(phase)
    severity = str(severity).upper()
    if severity not in ("INFO", "ERROR"):
        severity = "INFO"

    payload = {
        "schema_version": "registry.log.min.v3",
        "event_id": str(uuid.uuid4()),
        "ts": _now_iso_z(),
        "severity": severity,
        "op": op,
        "phase": phase,
        "req_id": req_id or "unknown",
        "actor_sub": actor_sub or "anonymous",
        "actor_tenant": actor_tenant or "default",
        "data": data or {},
    }
    if http_status is not None:
        payload["http_status"] = int(http_status)

    # Redis Stream에 JSON 직렬화 없이 field-value pairs로 기록 (필요 시 소비자가 JSON으로 재구성)
    # 단, data는 문자열로 직렬화하지 않고, op 키만 넣기 위해 간단 플랫닝
    # data = {op: {...}} 형태만 허용
    record = {k: str(v) for k, v in payload.items() if k != "data"}
    if error_code:
        record["error_code"] = error_code
    if error_msg:
        record["error_msg"] = error_msg
    # data[op] 블록을 data.op.* 이름공간으로 저장
    op_block = data.get(op, {}) if isinstance(data, dict) else {}
    for k, v in op_block.items():
        record[f"data.{op}.{k}"] = str(v)

    r = get_redis()
    r.xadd(current_app.config.get("LOG_V3_STREAM", LOG_V3_STREAM), record)


def read_events_v3(*, op: str | None = None, actor_sub: str | None = None, actor_tenant: str | None = None, target_id: str | None = None, limit: int = 50):
    """v3 로그 스트림을 조회하고 간단 필터를 적용하여 JSON 형태로 반환"""
    r = get_redis()
    stream = current_app.config.get("LOG_V3_STREAM", LOG_V3_STREAM)
    try:
        # 최신 이벤트 우선 조회
        entries = r.xrevrange(stream, max="+", min="-", count=limit)
    except Exception:
        entries = []
    out = []
    for _id, fields in entries:
        f = {k: v for k, v in fields.items()}
        if op and f.get("op") != op:
            continue
        if actor_sub and f.get("actor_sub") != actor_sub:
            continue
        if actor_tenant and f.get("actor_tenant") != actor_tenant:
            continue
        ev = format_event_from_fields(f)
        if target_id:
            # 지원되는 키들에서 대상 ID 매칭
            tid = block.get("target_id") or block.get("selected_id")
            if tid != target_id:
                continue
        out.append(ev)
        if len(out) >= limit:
            break
    return out


def format_event_from_fields(f: dict) -> dict:
    ev = {
        "schema_version": f.get("schema_version"),
        "event_id": f.get("event_id"),
        "ts": f.get("ts"),
        "severity": f.get("severity"),
        "op": f.get("op"),
        "phase": f.get("phase"),
        "req_id": f.get("req_id"),
        "actor_sub": f.get("actor_sub"),
        "actor_tenant": f.get("actor_tenant"),
    }
    if "http_status" in f:
        try:
            ev["http_status"] = int(f.get("http_status"))
        except Exception:
            pass
    if "error_code" in f:
        ev["error_code"] = f.get("error_code")
    if "error_msg" in f:
        ev["error_msg"] = f.get("error_msg")
    # data 복원
    op_name = ev.get("op")
    block = {}
    if op_name:
        prefix = f"data.{op_name}."
        for k, v in f.items():
            if k.startswith(prefix):
                block[k[len(prefix):]] = v
    ev["data"] = {op_name: block} if op_name else {}
    return ev
