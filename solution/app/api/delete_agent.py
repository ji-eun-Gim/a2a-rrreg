import os
import json
import secrets
from datetime import datetime, timezone, timedelta
from flask import request, jsonify

from . import api_bp
from ..core.auth import require_jwt, require_admin
from ..core.logging import append_log
from ..core import repo


def _now_utc9_iso() -> str:
    return datetime.now(timezone(timedelta(hours=9))).isoformat()


@api_bp.post('/delete-agent')
def delete_agent():
    # Auth
    err = require_jwt() or require_admin()
    if err:
        return err

    body = request.get_json(silent=True) or {}
    target_id = body.get('agent_id') if isinstance(body.get('agent_id'), str) else None

    # Fallback: derive from provided card
    if not target_id and isinstance(body.get('card'), dict):
        c = body['card']
        try:
            org = ''
            if isinstance(c.get('provider'), dict):
                org = str(c['provider'].get('organization') or '').strip()
            name_v = str(c.get('name') or '').strip()
            ver_v = str(c.get('version') or '').strip()
            if org and name_v and ver_v:
                target_id = f"{org}#agent:{name_v}.v{ver_v}"
            elif name_v and ver_v:
                target_id = f"agent:{name_v}.v{ver_v}"
        except Exception:
            target_id = None

    if not target_id:
        append_log('요청 오류 : agent_id 누락 (400 Bad Request)', False)
        return jsonify({"error": 'BAD_REQUEST', "message": 'agent_id is required'}), 400

    agents = repo.load_agents()
    idx = -1
    for i, rec in enumerate(agents):
        rid = rec.get('agent_id') if isinstance(rec, dict) else None
        if isinstance(rid, str) and rid == target_id:
            idx = i
            break
    if idx < 0:
        append_log('리소스 없음 : 대상 에이전트를 찾을 수 없음 (404 Not Found)', False)
        return jsonify({"error": 'NOT_FOUND', "message": 'agent not found'}), 404

    rec = agents[idx]
    name = (rec.get('card') or {}).get('name') if isinstance(rec.get('card'), dict) else ''
    # Update metadata: status and timestamps, bump version/etag
    now_local = _now_utc9_iso()
    version_id = int(rec.get('versionID', 1)) + 1
    rec['versionID'] = version_id
    rec['etag'] = f"W/\"{version_id}-{secrets.token_hex(3)}\""
    rec['status'] = 'Deleted'
    rec['update_ts'] = now_local
    rec['delete_ts'] = now_local

    repo.save_agents(agents)
    append_log(f"에이전트 삭제 성공 (200 OK): {name}", True)
    return jsonify({"agent": rec}), 200

