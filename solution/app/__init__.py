import os
import json
from typing import Any, Dict, List

from flask import Flask, jsonify, request, send_from_directory
from .core import repo
from .core.auth import require_jwt, require_admin
from .core.validators import validate_card_basic
from .core.logging import append_log


BASEDIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def ensure_dir():
    if not os.path.isdir(DATA_DIR):
        os.makedirs(DATA_DIR, exist_ok=True)


def ensure_files():
    """Ensure data directory and seed files via repo layer."""
    repo.ensure_seed()


def load_json(path: str, default: Any):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path: str, data: Any):
    ensure_dir()
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def is_non_empty_string(v: Any) -> bool:
    return isinstance(v, str) and v.trim() != '' if hasattr(v, 'trim') else isinstance(v, str) and v.strip() != ''


def is_string_array(v: Any) -> bool:
    return isinstance(v, list) and all(isinstance(x, str) for x in v)


def create_app() -> Flask:
    if os.path.isdir(os.path.join(BASEDIR, 'frontend')):
        static_root = os.path.join(BASEDIR, 'frontend')
    elif os.path.isdir(os.path.join(BASEDIR, 'webui', 'dist')):
        static_root = os.path.join(BASEDIR, 'webui', 'dist')
    else:
        static_root = os.path.join(BASEDIR, 'webui')
    app = Flask(__name__, static_folder=static_root, static_url_path='')
    # Ensure JSON responses keep Unicode (Korean) as-is
    app.config['JSON_AS_ASCII'] = False

    app.config['ADMIN_EMAIL'] = os.environ.get('ADMIN_EMAIL', 'admin@example.com')
    app.config['USERME_DIRECT_URL'] = os.environ.get('USERME_DIRECT_URL', 'http://127.0.0.1:8000/users/me')

    ensure_files()

    @app.after_request
    def _force_utf8(resp):
        try:
            ctype = resp.headers.get('Content-Type', '')
            if ('charset=' not in ctype) and (resp.mimetype and (resp.mimetype.startswith('text/') or resp.mimetype == 'application/json')):
                resp.headers['Content-Type'] = f"{resp.mimetype}; charset=utf-8"
        except Exception:
            pass
        return resp

    @app.get('/')
    def root():
        if os.path.exists(os.path.join(app.static_folder, 'dashboard.html')):
            return send_from_directory(app.static_folder, 'dashboard.html')
        return send_from_directory(app.static_folder, 'index.html')

    @app.get('/agents')
    def agents_page():
        # Prefer agents/index.html if present, fall back to agents/agents.html
        target_idx = os.path.join(app.static_folder, 'agents', 'index.html')
        if os.path.exists(target_idx):
            return send_from_directory(os.path.dirname(target_idx), os.path.basename(target_idx))
        target = os.path.join(app.static_folder, 'agents', 'agents.html')
        if os.path.exists(target):
            return send_from_directory(os.path.dirname(target), os.path.basename(target))
        return send_from_directory(app.static_folder, 'index.html')

    @app.get('/logs')
    def logs_page():
        target = os.path.join(app.static_folder, 'logs', 'logs.html')
        if os.path.exists(target):
            return send_from_directory(os.path.dirname(target), os.path.basename(target))
        return send_from_directory(app.static_folder, 'index.html')

    @app.get('/ruleset')
    def ruleset_page():
        target = os.path.join(app.static_folder, 'ruleset', 'ruleset.html')
        if os.path.exists(target):
            return send_from_directory(os.path.dirname(target), os.path.basename(target))
        return send_from_directory(app.static_folder, 'index.html')
    # Note: /api/auth/me is provided by the api blueprint (verify_jwt.py)

    def require_jwt_admin() -> Dict[str, Any]:
        auth = request.headers.get('Authorization', '')
        if not auth:
            return {"error": (401, 'TOKEN_MISSING', 'Missing Authorization header')}
        parts = auth.split(' ')
        if len(parts) != 2 or parts[0] != 'Bearer' or not parts[1]:
            return {"error": (401, 'INVALID_AUTH_FORMAT', 'Expected: Authorization: Bearer <token>')}
        result = get_user_me(parts[1], app.config['USERME_DIRECT_URL'])
        status = result.get('status')
        data = result.get('json') or {}
        if status == 200 and isinstance(data.get('email'), str):
            email = data['email']
            if email != app.config['ADMIN_EMAIL']:
                return {"error": (403, 'FORBIDDEN', 'Admin privileges required')}
            return {"email": email}
        if status == 401 and data.get('detail') == 'Invalid token':
            return {"error": (401, 'INVALID_TOKEN', 'Invalid or malformed token')}
        return {"error": (502, 'TOKEN_SERVICE_ERROR', 'Token service unavailable')}

    @app.get('/api/agents')
    def api_list_agents():
        raw = repo.load_agents()
        agents = []
        for item in raw:
            if isinstance(item, dict) and isinstance(item.get('card'), dict):
                card = item['card']
                name = card.get('name') if isinstance(card.get('name'), str) else None
                agents.append({
                    "agent_id": item.get('agent_id'),
                    "etag": item.get('etag'),
                    "versionID": item.get('versionID'),
                    "status": item.get('status', 'Active'),
                    "name": name or 'Unknown',
                    "card": card,
                    "create_ts": item.get('create_ts'),
                    "update_ts": item.get('update_ts'),
                    "delete_ts": item.get('delete_ts'),
                })
            else:
                agents.append(item)
        return jsonify({"agents": agents})

    @app.get('/api/logs')
    def api_get_logs():
        logs = repo.load_logs()
        return jsonify({"logs": logs})

    @app.post('/api/logs')
    def api_post_log():
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

    @app.post('/api/agents')
    def api_add_agent():
        auth = require_jwt_admin()
        if 'error' in auth:
            code, err, msg = auth['error']
            try:
                # Lazy import to avoid circular dependency on module load
                from app.core.logging import append_log
                if code == 403:
                    append_log('에이전트 추가 거부: 관리자 권한 아님 (403 Forbidden)', False)
                elif code == 401:
                    append_log('에이전트 추가 거부: 토큰 누락/형식 오류 (401 Unauthorized)', False)
                else:
                    append_log(f'에이전트 추가 거부: 토큰 서비스 오류 ({code})', False)
            except Exception:
                pass
            return jsonify({"error": err, "message": msg}), code

        body = request.get_json(silent=True) or {}
        card = body.get('card') if isinstance(body.get('card'), dict) else body

        v = validate_agent_card_basic(card)
        if not v['ok']:
            return jsonify({"error": 'REQUIRED_FIELDS_MISSING', "errors": v['errors']}), 422

        agents = load_json(AGENTS_FILE, [])
        name = str(card.get('name', ''))
        name_lc = name.lower()
        for a in agents:
            n = None
            if isinstance(a, dict):
                if isinstance(a.get('card'), dict):
                    n = a['card'].get('name')
                else:
                    n = a.get('name')
            if isinstance(n, str) and n.lower() == name_lc:
                return jsonify({"error": 'Agent already exists'}), 409

        agents.append({"card": card, "status": 'Active'})
        save_json(AGENTS_FILE, agents)
        try:
            from app.core.logging import append_log
            append_log(f"에이전트 추가 성공 (201 Created): {name}", True)
        except Exception:
            pass
        return jsonify({"agent": {"name": name, "status": 'Active', "card": card}}), 201

    # Register API blueprints within create_app
    from .api import api_bp
    app.register_blueprint(api_bp)

    return app






