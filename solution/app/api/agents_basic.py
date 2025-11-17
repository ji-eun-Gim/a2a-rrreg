from flask import jsonify, request

from . import api_bp
from ..core import repo
from ..core.auth import require_admin, require_jwt
from ..core.logging import append_log
from ..core.tenants import extract_tenants
from ..core.validators import validate_card_basic


# --- 에이전트 목록 조회 ---
@api_bp.get('/agents')
def list_agents():
    """등록된 모든 에이전트를 표준 메타데이터 형태로 반환."""
    err = require_jwt()
    if err:
        return err
    err = require_admin()
    if err:
        return err

    raw = repo.load_agents()
    agents = []
    for item in raw:
        if isinstance(item, dict) and isinstance(item.get('card'), dict):
            card = item['card']
            name = card.get('name') if isinstance(card.get('name'), str) else None
            agents.append(
                {
                    "agent_id": item.get('agent_id'),
                    "etag": item.get('etag'),
                    "versionID": item.get('versionID'),
                    "status": item.get('status', 'Active'),
                    "name": name or 'Unknown',
                    "card": card,
                    "tenants": item.get('tenants') if isinstance(item.get('tenants'), list) else [],
                    "create_ts": item.get('create_ts'),
                    "update_ts": item.get('update_ts'),
                    "delete_ts": item.get('delete_ts'),
                }
            )
        else:
            agents.append(item)
    return jsonify({"agents": agents})


# --- 간단 에이전트 등록 ---
@api_bp.post('/agents')
def add_agent():
    """관리자 전용 간단 등록 API."""
    err = require_jwt()
    if err:
        return err
    err = require_admin()
    if err:
        return err

    body = request.get_json(silent=True) or {}
    card = body.get('card') if isinstance(body.get('card'), dict) else body

    if not isinstance(card, dict):
        return jsonify({"error": 'REQUIRED_FIELDS_MISSING', "errors": ['card is required']}), 422

    tenants = []
    if isinstance(body, dict):
        tenants = extract_tenants(body.get('tenants'))
        if not tenants:
            # 과거 클라이언트가 metadata.tenants 에 값을 넣는 경우 보조 파싱
            tenants = extract_tenants(body.get('metadata'))

    ok, errors = validate_card_basic(card)
    if not ok:
        return jsonify({"error": 'REQUIRED_FIELDS_MISSING', "errors": errors}), 422

    agents = repo.load_agents()
    name = str(card.get('name', '') or '')
    name_lc = name.lower()
    # name 기준 중복 확인
    for existing in agents:
        # 각 레코드를 순회하며 name 을 꺼내 비교
        existing_name = None
        if isinstance(existing, dict):
            if isinstance(existing.get('card'), dict):
                existing_name = existing['card'].get('name')
            else:
                existing_name = existing.get('name')
        if isinstance(existing_name, str) and existing_name.lower() == name_lc:
            return jsonify({"error": 'Agent already exists'}), 409

    agents.append({"card": card, "status": 'Active', "tenants": tenants})
    repo.save_agents(agents)

    try:
        append_log(f"에이전트 추가 성공 (201 Created): {name}", True)
    except Exception:
        pass

    return jsonify({"agent": {"name": name, "status": 'Active', "card": card, "tenants": tenants}}), 201
