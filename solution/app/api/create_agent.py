import os
import json
import secrets
from datetime import datetime, timezone, timedelta
from flask import request, jsonify
import secrets
from datetime import datetime, timezone, timedelta

from . import api_bp
from ..core.auth import require_jwt, require_admin
from ..core.logging import append_log
from ..core import repo
from ..core.validators import (
    validate_card_basic,
    DEFAULT_MAX_AGENT_CARD_BYTES,
)
from ..core.signatures import validate_signatures_jws_like
from ..core.policy import check_duplicate_card, PolicyEvaluator
from ..core.tenants import extract_tenants
import requests

# JWS-server config (optional auto-sign)
JWS_SERVER_URL = os.environ.get('JWS_SERVER_URL', 'http://127.0.0.1:8001')
JWS_SIGN_URL = f"{JWS_SERVER_URL.rstrip('/')}/sign"
DEFAULT_JWS_KID = os.environ.get('JWS_KID', 'registry-hs256-key-1')


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

    # Capture tenant list
    tenants = []
    if isinstance(body, dict):
        tenants = extract_tenants(body.get('tenants'))

    if not tenants:
        append_log('스키마 검증 실패 : tenant 선택 누락 (422 Unprocessable Entity)', False)
        return jsonify({"error": 'TENANT_REQUIRED', "message": 'at least one tenant must be specified'}), 422

    # Capture any publisher-provided signatures to move into metadata later
    original_sigs = card.get('signatures') if isinstance(card.get('signatures'), list) else []

    # If no signatures or publisher signatures exist, try registry auto-sign (best-effort)
    try:
        # Always sign if missing, or replace publisher signatures with registry signature
        need_sign = not original_sigs or True
        if need_sign:
            # derive subject
            def _derive_sub_from_card(c: dict) -> str:
                try:
                    org = ''
                    if isinstance(c.get('provider'), dict):
                        org = str(c['provider'].get('organization') or '').strip()
                    name_v = str(c.get('name') or '').strip()
                    ver_v = str(c.get('version') or '').strip()
                    if org and name_v and ver_v:
                        return f"{org}#agent:{name_v}.v{ver_v}"
                    if name_v and ver_v:
                        return f"agent:{name_v}.v{ver_v}"
                    return name_v or 'agent:unknown'
                except Exception:
                    return 'agent:unknown'

            sign_payload = {
                'sub': _derive_sub_from_card(card),
                'version_id': 1,
                'policy_version': os.environ.get('POLICY_VERSION', 'registry.policy.v3'),
                'iss': os.environ.get('JWS_ISS', 'ans-registry.example'),
                'kid': DEFAULT_JWS_KID,
                'card': card,
            }
            try:
                r = requests.post(JWS_SIGN_URL, json=sign_payload, timeout=5)
                if r.ok:
                    data = r.json()
                    token = data.get('jws')
                    parts = token.split('.') if isinstance(token, str) else []
                    if len(parts) == 3:
                        protected_b64, _payload_b64, signature_b64 = parts
                        sig_entry = {
                            'protected': protected_b64,
                            'signature': signature_b64,
                            'header': {'kid': DEFAULT_JWS_KID},
                        }
                        # Replace any publisher signatures on the card with registry signature
                        card['signatures'] = [sig_entry]
                        try:
                            append_log('JWS 자동 서명 성공 : 시그니처 추가', True)
                        except Exception:
                            pass
            except Exception:
                # auto-sign best-effort; proceed to normal validation
                pass
    except Exception:
        pass

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
            # 표준화된 서명 불일치 로그
            append_log('스키마 검증 실패 : 시그니처 필드의 JWS 불일치 (498 Invalid Token)', False)
        except Exception:
            pass
        # 498: Invalid Token (non-standard), requested mapping
        return jsonify({"error": 'INVALID_TOKEN', "message": sig_reason or 'Invalid JWS signature'}), 498

    agents = repo.load_agents()
    dup = check_duplicate_card(card, agents)
    if isinstance(dup, str) and dup:
        try:
            # 표준화된 정책 실패 로그 메시지
            append_log('정책 검사 실패 : 동일 name/url 이 존재 (409 Conflict)', False)
        except Exception:
            pass
        return jsonify({"error": 'CONFLICT', "message": dup}), 409

    # 도메인 / IP 화이트리스트 검사 (.env 기반)
    try:
        evaluator = PolicyEvaluator()  # env에서 AGENT_DOMAIN_WHITELIST, AGENT_IP_WHITELIST 읽음
        wle = evaluator._check_whitelist(card)
    except Exception:
        wle = None
    if isinstance(wle, str) and wle:
        try:
            append_log('정책 검사 실패 : 도메인/IP 화이트리스트 불일치 (400 Bad Request)', False)
        except Exception:
            pass
        return jsonify({"error": 'WHITELIST_REJECTED', "message": wle}), 400

    name = str(card.get('name', ''))

    # Build agent metadata record
    def _derive_agent_id(c: dict) -> str:
        try:
            org = ''
            if isinstance(c.get('provider'), dict):
                org = str(c['provider'].get('organization') or '').strip()
            name_v = str(c.get('name') or '').strip()
            ver_v = str(c.get('version') or '').strip()
            if org and name_v and ver_v:
                return f"{org}#agent:{name_v}.v{ver_v}"
            if name_v and ver_v:
                return f"agent:{name_v}.v{ver_v}"
            return name_v or 'agent:unknown'
        except Exception:
            return 'agent:unknown'

    # timestamps in UTC+9
    jst = timezone(timedelta(hours=9))
    now_local = datetime.now(jst).isoformat()

    # ETag and version
    version_id = 1
    short = secrets.token_hex(3)
    etag = f"W/\"{version_id}-{short}\""

    # optional publisher JWS from request body or move original signatures
    publisher_jws = None
    try:
        publisher_jws = (
            body.get('publisher_jws')
            or body.get('publisherJws')
            or body.get('jws')
        )
        if not isinstance(publisher_jws, str):
            publisher_jws = None
    except Exception:
        publisher_jws = None

    # If the incoming card had signatures, move them into publisher_jws (metadata)
    if not publisher_jws and original_sigs:
        # store the original signature entries as-is in metadata
        publisher_jws = original_sigs

    # registrant from JWT
    try:
        from flask import g
        registrant = getattr(g, 'jwt', {}).get('sub')
    except Exception:
        registrant = None

    record = {
        "agent_id": _derive_agent_id(card),
        "etag": etag,
        "versionID": version_id,
        "card": card,
        "status": 'Active',
        "tenants": tenants,
        "create_ts": now_local,
        "update_ts": now_local,
        "delete_ts": None,
        "publisher_jws": publisher_jws,
        "registrant": registrant,
    }

    agents.append(record)
    repo.save_agents(agents)
    append_log(f"에이전트 추가 성공 (201 Created): {name}", True)
    return jsonify({"agent": {"name": name, "status": 'Active', "card": card, "tenants": tenants}}), 201




