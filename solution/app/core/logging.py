import os
import json
from datetime import datetime

DATA_ROOT_OVERRIDE = os.environ.get("SOLUTION_DATA_ROOT")
# Use solution/data at project root (or override for tests)
_ROOT_DIR = os.path.abspath(DATA_ROOT_OVERRIDE) if DATA_ROOT_OVERRIDE else os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..')
)
_DATA_DIR = os.path.join(_ROOT_DIR, 'data')
_LOG_FILE = os.path.join(_DATA_DIR, 'log.json')
MAX_LOG_ENTRIES = int(os.environ.get("SOLUTION_MAX_LOG_ENTRIES", "500"))


def _ensure_log_file():
    os.makedirs(_DATA_DIR, exist_ok=True)
    if not os.path.exists(_LOG_FILE):
        with open(_LOG_FILE, 'w', encoding='utf-8') as f:
            f.write('[]')


def _k_time_label(dt: datetime) -> str:
    return f"{dt.hour:02d}시 {dt.minute:02d}분 {dt.second:02d}초"


def append_log(message: str, ok: bool, when: datetime | None = None):
    try:
        _ensure_log_file()
        when = when or datetime.now()
        try:
            with open(_LOG_FILE, 'r', encoding='utf-8') as f:
                logs = json.load(f)
        except Exception:
            logs = []
        entry = {
            'message': str(message or ''),
            'ok': bool(ok),
            'timeIso': when.isoformat(),
            'timeText': _k_time_label(when),
        }
        logs.insert(0, entry)
        if isinstance(logs, list) and len(logs) > MAX_LOG_ENTRIES:
            del logs[MAX_LOG_ENTRIES:]
        with open(_LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)
    except Exception:
        # Never break primary flow due to logging
        pass
