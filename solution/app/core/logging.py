import os
import json
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

# --- 프로젝트 데이터/로그 파일 경로 ---
DATA_ROOT_OVERRIDE = os.environ.get("SOLUTION_DATA_ROOT")
_ROOT_DIR = (
    os.path.abspath(DATA_ROOT_OVERRIDE)
    if DATA_ROOT_OVERRIDE
    else os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
)
_DATA_DIR = os.path.join(_ROOT_DIR, 'data')
_LOG_DIR = os.path.join(_DATA_DIR, 'redisDB')
_LOG_FILE = os.path.join(_LOG_DIR, 'logs.json')
_OLD_LOG_FILE = os.path.join(_DATA_DIR, 'log.json')
MAX_LOG_ENTRIES = int(os.environ.get("SOLUTION_MAX_LOG_ENTRIES", "500"))


def _ensure_log_file():
    """data/redisDB/logs.json 파일을 생성 (기존 data/log.json 있으면 가져옴)."""
    os.makedirs(_LOG_DIR, exist_ok=True)
    if not os.path.exists(_LOG_FILE):
        # migrate from old location if present
        if os.path.exists(_OLD_LOG_FILE):
            try:
                with open(_OLD_LOG_FILE, 'r', encoding='utf-8') as src:
                    content = src.read()
                with open(_LOG_FILE, 'w', encoding='utf-8') as dst:
                    dst.write(content)
                return
            except Exception:
                pass
        with open(_LOG_FILE, 'w', encoding='utf-8') as f:
            f.write('[]')


def _k_time_label(dt: datetime) -> str:
    return f"{dt.hour:02d}시 {dt.minute:02d}분 {dt.second:02d}초"


def _now_kst() -> datetime:
    """현재 한국 표준시(UTC+9)로 시간을 반환."""
    try:
        return datetime.now(ZoneInfo("Asia/Seoul"))
    except Exception:
        # zoneinfo 가 없거나 실패하면 서버 로컬 시간으로 대체
        return datetime.now()


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
    """플랫폼/공용 로그 파일에 추가."""
    try:
        _ensure_log_file()
        when = when or _now_kst()
        if when.tzinfo is None:
            try:
                when = when.replace(tzinfo=ZoneInfo("Asia/Seoul"))
            except Exception:
                pass
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
        # 로깅 중 오류가 발생해도 앱 흐름은 유지
        pass
