import copy
import os
import json

# --- 프로젝트 루트의 solution/data 디렉터리 경로 ---
_ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
_DATA_DIR = os.path.join(_ROOT_DIR, 'data')
_AGENTS_DIR = os.path.join(_DATA_DIR, 'redisDB')
AGENTS_FILE = os.path.join(_AGENTS_DIR, 'agents.json')
LOG_FILE = os.path.join(_AGENTS_DIR, 'logs.json')
RULESETS_FILE = os.path.join(_AGENTS_DIR, 'rulesets.json')
_OLD_LOG_FILE = os.path.join(_DATA_DIR, 'log.json')
_OLD_RULESETS_FILE = os.path.join(_DATA_DIR, 'rulesets.json')

DEFAULT_RULESETS = [
    {
        "ruleset_id": "prompt_validation_customer",
        "name": "고객 정보 프롬프트 검증",
        "type": "prompt_validation",
        "description": "고객 요청 프롬프트가 기밀 정보를 포함하지 않도록 검증합니다.",
        "enabled": True,
        "system_prompt": "당신은 고객 정보 검색을 담당하는 에이전트입니다. 민감한 고객 데이터를 외부에 노출하지 마세요.",
        "model": "gemini-2.0-flash",
        "created_at": "2025-11-18T10:30:00Z",
        "updated_at": "2025-11-18T10:30:00Z",
    },
    {
        "ruleset_id": "prompt_validation_delivery",
        "name": "배송 검증 프롬프트",
        "type": "prompt_validation",
        "description": "배송 업데이트 관련 질문만 처리하도록 프롬프트를 제한합니다.",
        "enabled": True,
        "system_prompt": "당신은 배송 현황을 요약하는 에이전트입니다. 주문 번호 외의 개인 정보는 요청하지 마세요.",
        "model": "gemini-2.0",
        "created_at": "2025-11-18T10:45:00Z",
        "updated_at": "2025-11-18T10:45:00Z",
    },
    {
        "ruleset_id": "tool_validation_integration",
        "name": "툴 호출 검증",
        "type": "tool_validation",
        "description": "허용된 에이전트와 파라미터인지 확인합니다.",
        "enabled": True,
        "tool_name": "call_remote_agent",
        "rules": {
            "allowed_agents": [
                "oneth.ai#agent:CustomerAgent.v1.0.0",
                "oneth.ai#agent:Delivery Agent.v1.0.0"
            ],
            "max_calls_per_minute": 20
        },
        "created_at": "2025-11-18T11:00:00Z",
        "updated_at": "2025-11-18T11:00:00Z",
    },
    {
        "ruleset_id": "response_filtering_default",
        "name": "응답 필터링 기본룰",
        "type": "response_filtering",
        "description": "비밀번호나 토큰같이 민감한 단어를 검출하여 마스킹합니다.",
        "enabled": True,
        "blocked_keywords": ["secret", "password", "jwt", "credentials"],
        "created_at": "2025-11-18T11:05:00Z",
        "updated_at": "2025-11-18T11:05:00Z",
    },
]


def _ensure_data_dir():
    os.makedirs(_DATA_DIR, exist_ok=True)
    os.makedirs(_AGENTS_DIR, exist_ok=True)  # data/redisDB 경로에 에이전트 저장


def ensure_seed():
    """data 디렉터리 및 초기 JSON 파일이 없으면 생성."""
    _ensure_data_dir()
    if not os.path.exists(AGENTS_FILE):
        with open(AGENTS_FILE, 'w', encoding='utf-8') as f:
            json.dump([], f, ensure_ascii=False, indent=2)
    if not os.path.exists(LOG_FILE):
        try:
            if os.path.exists(_OLD_LOG_FILE):
                with open(_OLD_LOG_FILE, 'r', encoding='utf-8') as src:
                    data = src.read()
                with open(LOG_FILE, 'w', encoding='utf-8') as dst:
                    dst.write(data)
            else:
                with open(LOG_FILE, 'w', encoding='utf-8') as f:
                    f.write('[]')
        except Exception:
            with open(LOG_FILE, 'w', encoding='utf-8') as f:
                f.write('[]')
    if not os.path.exists(RULESETS_FILE):
        try:
            if os.path.exists(_OLD_RULESETS_FILE):
                with open(_OLD_RULESETS_FILE, 'r', encoding='utf-8') as src:
                    data = json.load(src)
                with open(RULESETS_FILE, 'w', encoding='utf-8') as dst:
                    json.dump(data, dst, ensure_ascii=False, indent=2)
            else:
                with open(RULESETS_FILE, 'w', encoding='utf-8') as f:
                    json.dump(DEFAULT_RULESETS, f, ensure_ascii=False, indent=2)
        except Exception:
            with open(RULESETS_FILE, 'w', encoding='utf-8') as f:
                json.dump(DEFAULT_RULESETS, f, ensure_ascii=False, indent=2)


def load_json(path: str, default):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path: str, data):
    _ensure_data_dir()
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_agents():
    ensure_seed()
    return load_json(AGENTS_FILE, [])


def save_agents(data):
    save_json(AGENTS_FILE, data)


def load_logs():
    ensure_seed()
    return load_json(LOG_FILE, [])


def save_logs(data):
    save_json(LOG_FILE, data)


def load_rulesets():
    ensure_seed()
    return load_json(RULESETS_FILE, copy.deepcopy(DEFAULT_RULESETS))


def save_rulesets(data):
    save_json(RULESETS_FILE, data)
