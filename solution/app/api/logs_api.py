"""레지스트리 로그를 조회/추가하는 간단한 API (디버깅 용도)."""

from flask import jsonify, request

from . import api_bp
from ..core import repo

# --- 로그 조회 ---
@api_bp.get('/logs')
def get_logs():
    """레지스트리 활동 로그 전체를 반환."""
    logs = repo.load_logs()
    return jsonify({"logs": logs})


# --- 로그 추가 ---
@api_bp.post('/logs')
def append_log_entry():
    """로그 항목을 직접 추가(파일 append)."""
    body = request.get_json(silent=True) or {}
    message = body.get('message') if isinstance(body.get('message'), str) else ''
    if not message:
        return jsonify({"error": 'message is required'}), 400

    ok = bool(body.get('ok'))
    time_iso = body.get('timeIso') if isinstance(body.get('timeIso'), str) else None
    time_text = body.get('timeText') if isinstance(body.get('timeText'), str) else ''

    # core.logging 을 거치지 않고 직접 파일에 적재 (테스트/이관용)
    logs = repo.load_logs()
    entry = {"message": message, "ok": ok, "timeIso": time_iso, "timeText": time_text}
    logs.insert(0, entry)
    repo.save_logs(logs)
    return jsonify({"log": entry}), 201
