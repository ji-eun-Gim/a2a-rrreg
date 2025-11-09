from __future__ import annotations
from .schema import AGENT_CARD_SCHEMA_V1, RECOMMENDED_FIELDS
from jsonschema import Draft7Validator


validator = Draft7Validator(AGENT_CARD_SCHEMA_V1)


def validate_agent_card(card: dict):
    # JSON Schema 기반 유효성 검사 + 권장 필드 경고 수집
    errors = []
    for e in validator.iter_errors(card):
        path = "/" + "/".join([str(p) for p in e.path])
        errors.append({"path": path if path != "/" else "", "msg": e.message})
    valid = len(errors) == 0

    warnings = []
    # 권장 필드 힌트 생성
    def has_path(d: dict, dotted: str) -> bool:
        cur = d
        for part in dotted.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                return False
        return True

    for dotted, msg in RECOMMENDED_FIELDS:
        if not has_path(card, dotted):
            warnings.append({"path": dotted.replace(".", "/"), "msg": msg})

    return valid, errors, warnings
