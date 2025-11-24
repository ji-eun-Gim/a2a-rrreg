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


_BASE64URL_CHARS = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")


def _is_base64url(text: str) -> bool:
    if not isinstance(text, str) or text == "":
        return False
    for ch in text:
        if ch == '=':
            continue
        if ch not in _BASE64URL_CHARS:
            return False
    return True


def _allowed_algs() -> set[str]:
    raw = os.environ.get("ALLOWED_JWS_ALGS", "ES256,RS256,HS256")
    return {alg.strip() for alg in raw.split(',') if alg.strip()}


def verify_jws(card: Dict[str, Any]) -> Tuple[bool, str]:
    """JWS(JSON Serialization) 형태 유사성 검증(암호학적 검증 아님).

    - signatures[*].protected: base64url 디코드 → JSON 파싱 가능해야 함
    - signatures[*].signature: base64url 디코드 가능해야 함
    - header.kid 와 protected 헤더의 kid(있다면)가 일치해야 함

    반환값:
      - 모든 검증 통과 시 (True, "")
      - 실패 시 (False, 실패 사유 문자열)
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
        if not _is_base64url(prot):
            return False, f'signatures[{i}].protected is not base64url'
        try:
            prot_bytes = _b64url_decode(prot)
            prot_json = json.loads(prot_bytes.decode('utf-8'))
            if not isinstance(prot_json, dict):
                return False, f'signatures[{i}].protected must decode to a JSON object'
        except Exception:
            return False, f'signatures[{i}].protected is not valid base64url JSON'
        try:
            if not _is_base64url(raw_sig):
                raise ValueError("not base64url")
            _ = _b64url_decode(raw_sig)
        except Exception:
            return False, f'signatures[{i}].signature is not valid base64url'
        # alg 값은 필수이며 허용 목록에 포함되어야 함
        alg = prot_json.get('alg')
        if not isinstance(alg, str) or not alg.strip():
            return False, f'signatures[{i}].protected.alg missing'
        if alg.strip() not in _allowed_algs():
            return False, f'signatures[{i}].protected.alg not allowed'
        # kid 값도 필수이며 header.kid 와 일치해야 함
        kid_in_protected = prot_json.get('kid')
        if not isinstance(kid_in_protected, str) or not kid_in_protected.strip():
            return False, f'signatures[{i}].protected.kid missing'
        if kid_in_protected.strip() != hdr.get('kid').strip():
            return False, f'signatures[{i}].header.kid mismatch with protected header'
    return True, ''


def validate_signatures_jws_like(card: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Backward-compatible alias used by API layer.
    Performs the same structural checks as verify_jws.
    """
    return verify_jws(card)


__all__ = [
    'verify_jws',
    'validate_signatures_jws_like',
]
