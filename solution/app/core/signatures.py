"""
JWS 관련 서명 유틸리티.

현재는 구조적(JWS‑like) 검증만 제공하며, 암호학적 검증은 포함하지 않음.
"""

from __future__ import annotations

import json
import base64
from typing import Any, Dict, Tuple
import os


def _b64url_decode(data: str) -> bytes:
    data = data.strip()
    pad = '=' * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def _allowed_algs() -> set[str]:
    raw = os.environ.get("ALLOWED_JWS_ALGS", "ES256,RS256,HS256")
    return {alg.strip() for alg in raw.split(',') if alg.strip()}


def validate_signatures_jws_like(card: Dict[str, Any]) -> Tuple[bool, str]:
    """JWS(JSON Serialization) 형태 유사성 검증(암호학적 검증 아님).

    - signatures[*].protected: base64url 디코드 → JSON 파싱 가능해야 함
    - signatures[*].signature: base64url 디코드 가능해야 함
    - header.kid 와 protected 헤더의 kid(있다면)가 일치해야 함

    Returns:
      (True, "") if all signatures pass structural checks
      (False, reason) otherwise
    """
    sigs = card.get('signatures')
    if not isinstance(sigs, list) or not sigs:
        return False, 'signatures missing or empty'
    for i, sig in enumerate(sigs):
        if not isinstance(sig, dict):
            return False, f'signatures[{i}] must be an object'
        prot = sig.get('protected')
        raw_sig = sig.get('signature')
        hdr = sig.get('header')
        if not isinstance(prot, str) or not prot.strip():
            return False, f'signatures[{i}].protected missing'
        if not isinstance(raw_sig, str) or not raw_sig.strip():
            return False, f'signatures[{i}].signature missing'
        if not isinstance(hdr, dict) or not isinstance(hdr.get('kid'), str) or not hdr.get('kid').strip():
            return False, f'signatures[{i}].header.kid missing'
        try:
            prot_bytes = _b64url_decode(prot)
            prot_json = json.loads(prot_bytes.decode('utf-8'))
            if not isinstance(prot_json, dict):
                return False, f'signatures[{i}].protected must decode to a JSON object'
        except Exception:
            return False, f'signatures[{i}].protected is not valid base64url JSON'
        try:
            _ = _b64url_decode(raw_sig)
        except Exception:
            return False, f'signatures[{i}].signature is not valid base64url'
        # alg must be present and allowed
        alg = prot_json.get('alg')
        if not isinstance(alg, str) or not alg.strip():
            return False, f'signatures[{i}].protected.alg missing'
        if alg.strip() not in _allowed_algs():
            return False, f'signatures[{i}].protected.alg not allowed'
        # kid must be present and match header.kid
        kid_in_protected = prot_json.get('kid')
        if not isinstance(kid_in_protected, str) or not kid_in_protected.strip():
            return False, f'signatures[{i}].protected.kid missing'
        if kid_in_protected.strip() != hdr.get('kid').strip():
            return False, f'signatures[{i}].header.kid mismatch with protected header'
    return True, ''


__all__ = [
    'validate_signatures_jws_like',
]
