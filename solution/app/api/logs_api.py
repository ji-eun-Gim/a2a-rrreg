from flask import jsonify, request

from . import api_bp
from ..core import repo


@api_bp.get('/logs')
def get_logs():
    """Return registry activity logs."""
    logs = repo.load_logs()
    return jsonify({"logs": logs})


@api_bp.post('/logs')
def append_log_entry():
    """Append a log entry to the registry log store."""
    body = request.get_json(silent=True) or {}
    message = body.get('message') if isinstance(body.get('message'), str) else ''
    if not message:
        return jsonify({"error": 'message is required'}), 400

    ok = bool(body.get('ok'))
    time_iso = body.get('timeIso') if isinstance(body.get('timeIso'), str) else None
    time_text = body.get('timeText') if isinstance(body.get('timeText'), str) else ''

    logs = repo.load_logs()
    entry = {"message": message, "ok": ok, "timeIso": time_iso, "timeText": time_text}
    logs.insert(0, entry)
    repo.save_logs(logs)
    return jsonify({"log": entry}), 201
