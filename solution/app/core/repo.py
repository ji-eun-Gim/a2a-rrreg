import os
import json

_ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
_DATA_DIR = os.path.join(_ROOT_DIR, 'data')
AGENTS_FILE = os.path.join(_DATA_DIR, 'agents.json')
LOG_FILE = os.path.join(_DATA_DIR, 'log.json')


def _ensure_data_dir():
    os.makedirs(_DATA_DIR, exist_ok=True)


def ensure_seed():
    """Ensure data directory and seed files exist."""
    _ensure_data_dir()
    if not os.path.exists(AGENTS_FILE):
        seed = [
            {"name": "Orchestrator", "status": "Active"},
            {"name": "Agent1", "status": "Active"},
            {"name": "Agent2", "status": "Active"},
            {"name": "Agent3", "status": "Active"},
            {"name": "Agent4", "status": "Active"},
            {"name": "Bridge", "status": "Active"},
        ]
        with open(AGENTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(seed, f, ensure_ascii=False, indent=2)
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            f.write('[]')


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

