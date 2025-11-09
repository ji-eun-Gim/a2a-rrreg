# 에이전트 카드 JSON Schema v1 (필수/권장 필드 정의)
AGENT_CARD_SCHEMA_V1 = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "https://example.com/schemas/agent-card.json",
    "type": "object",
    "required": ["name", "version", "protocolVersion", "url", "skills"],
    "properties": {
        "name": {"type": "string", "minLength": 1},
        "namespace": {"type": "string"},
        "version": {"type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$"},
        "protocolVersion": {"type": "string"},
        "url": {"type": "string", "format": "uri"},
        "skills": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["id", "name", "description"],
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                },
                "additionalProperties": True,
            },
        },
        "endpoints": {"type": "object"},
        "authentication": {"type": "object"},
        "defaultInputModes": {"type": "array"},
        "defaultOutputModes": {"type": "array"},
        "contact": {
            "type": "object",
            "properties": {
                "email": {"type": "string"}
            },
        },
        "tags": {"type": "array", "items": {"type": "string"}},
    },
    "additionalProperties": True,
}

# 권장 필드 목록 (존재하지 않을 시 경고 노출 전용)
RECOMMENDED_FIELDS = [
    ("namespace", "Recommended to group related agents"),
    ("endpoints", "Recommended to describe service endpoints"),
    ("authentication", "Recommended to describe auth methods"),
    ("defaultInputModes", "Recommended to describe defaults"),
    ("defaultOutputModes", "Recommended to describe defaults"),
    ("contact.email", "Recommended to provide contact"),
]
