import os
import json
from datetime import datetime
from typing import Optional

# --- 프로젝트 데이터 디렉터리/로그 파일 경로 ---
DATA_ROOT_OVERRIDE = os.environ.get("SOLUTION_DATA_ROOT")
_ROOT_DIR = (
    os.path.abspath(DATA_ROOT_OVERRIDE)
    if DATA_ROOT_OVERRIDE
    else os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
)
_DATA_DIR = os.path.join(_ROOT_DIR, 'data')
_LOG_FILE = os.path.join(_DATA_DIR, 'log.json')
MAX_LOG_ENTRIES = int(os.environ.get("SOLUTION_MAX_LOG_ENTRIES", "500"))


def _ensure_log_file():
    """data/log.json 파일이 없으면 생성."""
    os.makedirs(_DATA_DIR, exist_ok=True)
    if not os.path.exists(_LOG_FILE):
        with open(_LOG_FILE, 'w', encoding='utf-8') as f:
            f.write('[]')


def _k_time_label(dt: datetime) -> str:
    return f"{dt.hour:02d}시 {dt.minute:02d}분 {dt.second:02d}초"


def _request_ip() -> Optional[str]:
    """Flask request 컨텍스트에서 클라이언트 IP 추출 (가능한 경우)."""
    try:
        from flask import request  # type: ignore

        if not request:
            return None
        forwarded = request.headers.get('X-Forwarded-For')
        if forwarded:
            return forwarded.split(',')[0].strip()
        return request.remote_addr
    except Exception:
        return None


def append_log(
    message: str,
    ok: bool,
    when: datetime | None = None,
    *,
    capture_client_ip: bool = False,
    client_ip: str | None = None,
):
    """레지스트리 공용 로그 파일에 항목을 추가."""
    try:
        _ensure_log_file()
        when = when or datetime.now()
        try:
            with open(_LOG_FILE, 'r', encoding='utf-8') as f:
                logs = json.load(f)
        except Exception:
            logs = []
        ip = client_ip or (_request_ip() if capture_client_ip else None)
        entry = {
            'message': str(message or ''),
            'ok': bool(ok),
            'timeIso': when.isoformat(),
            'timeText': _k_time_label(when),
        }
        if ip:
            entry['clientIp'] = ip
        logs.insert(0, entry)
        if isinstance(logs, list) and len(logs) > MAX_LOG_ENTRIES:
            del logs[MAX_LOG_ENTRIES:]
        with open(_LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)
    except Exception:
        # 로깅 중 오류가 발생해도 본 흐름을 끊지 않음
        pass
