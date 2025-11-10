import os
import json
from flask import request, jsonify

from . import api_bp
from ..core.auth import require_jwt, require_admin
from ..core.logging import append_log
from ..core import repo
from ..core.validators import (
    validate_card_basic,
    DEFAULT_MAX_AGENT_CARD_BYTES,
)
from ..core.signatures import validate_signatures_jws_like


# Data access via app.core.repo

@api_bp.post('/create-agent')
def create_agent():
    # Auth checks with logging on failures
    err = require_jwt()
    if err:
        status = err[1] if isinstance(err, tuple) and len(err) > 1 else 500
        if status == 401:
            append_log('에이전트 추가 거부: 토큰 누락/유효하지 않음 (401 Unauthorized)', False)
        else:
            append_log(f'에이전트 추가 거부: 토큰 서비스 오류 ({status})', False)
        return err
    err2 = require_admin()
    if err2:
        append_log('에이전트 추가 거부: 관리자 권한 아님 (403 Forbidden)', False)
        return err2

    # Raw body for size + JSON syntax validation
    raw = request.get_data(as_text=True) or ''
    try:
        byte_len = len(raw.encode('utf-8'))
        if byte_len > DEFAULT_MAX_AGENT_CARD_BYTES:
            # 표준화된 로그 메시지 (요청 포맷)
            append_log('스키마 검증 실패 : 에이전트 최대 바이트 넘김 (413 Payload Too Larg)', False)
            return jsonify({"error": 'PAYLOAD_TOO_LARGE', "message": f"payload exceeds {DEFAULT_MAX_AGENT_CARD_BYTES} bytes"}), 413
    except Exception:
        pass
    try:
        body = json.loads(raw)
    except Exception:
        append_log('스키마 검증 실패 : 잘못된 JSON 문법 (400 Bad Request)', False)
        return jsonify({"error": 'BAD_JSON', "message": 'Invalid JSON'}), 400

    # Accept both wrapped and bare card payloads
    card = None
    if isinstance(body, dict):
        if isinstance(body.get('card'), dict):
            card = body.get('card')
        else:
            card = body
    # Explicit handling for missing/invalid card object
    if not isinstance(card, dict):
        append_log('스키마 검증 실패 :   card 필드 누락', False)
        return jsonify({"error": 'REQUIRED_FIELDS_MISSING', "errors": ['card is required']}), 422
 
    # Basic field-level validation (schema-lite)
    ok, errors = validate_card_basic(card)
    if not ok:
        try:
            # 표준화된 422 로그 메시지
            append_log('스키마 검증 실패 : 필수 필드 누락 (422 Unprocessable Entity)', False)
        except Exception:
            pass
        return jsonify({"error": 'REQUIRED_FIELDS_MISSING', "errors": errors}), 422

    # JWS-like signature structure checks (no crypto verification)
    sig_ok, sig_reason = validate_signatures_jws_like(card)
    if not sig_ok:
        try:
            append_log(f'서명 검증 실패 :   {sig_reason}', False)
        except Exception:
            pass
        # 498: Invalid Token (non-standard), requested mapping
        return jsonify({"error": 'INVALID_TOKEN', "message": sig_reason or 'Invalid JWS signature'}), 498

    agents = repo.load_agents()
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
    repo.save_agents(agents)
    append_log(f"에이전트 추가 성공 (201 Created): {name}", True)
    return jsonify({"agent": {"name": name, "status": 'Active', "card": card}}), 201




