from __future__ import annotations
import threading
import time
import sys
import uuid
from typing import Optional, Set

import requests
from flask import Flask

from ..core.redis_client import get_redis
from ..core.log_v3 import format_event_from_fields


class LogForwarder:
    def __init__(self, app: Flask):
        self.app = app
        self.thread: Optional[threading.Thread] = None
        self.stop_evt = threading.Event()

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.stop_evt.clear()
        self.thread = threading.Thread(target=self._run, name="log-forwarder", daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_evt.set()

    def _run(self):
        with self.app.app_context():
            url = self.app.config.get("LOG_FORWARD_URL")
            if not url:
                return
            token = self.app.config.get("LOG_FORWARD_TOKEN")
            ops_raw = self.app.config.get("LOG_FORWARD_OPS")  # comma-separated
            allow_ops: Optional[Set[str]] = None
            if ops_raw:
                allow_ops = {o.strip() for o in str(ops_raw).split(",") if o.strip()}

            stream = self.app.config.get("LOG_V3_STREAM", "log:v3")
            r = get_redis(self.app)
            # Single-runner lock to prevent duplicate forwarding across multiple workers
            lock_key = self.app.config.get("LOG_FORWARD_LOCK_KEY", "log_forwarder:lock")
            lock_val = str(uuid.uuid4())
            try:
                got_lock = False
                try:
                    got_lock = bool(r.set(lock_key, lock_val, nx=True, ex=30))
                except Exception:
                    got_lock = True  # if redis unavailable, best-effort: do not block
                if not got_lock:
                    return
            except Exception:
                return
            last_id = "$"  # start from new entries only
            headers = {"Content-Type": "application/json; charset=utf-8"}
            if token:
                headers["Authorization"] = f"Bearer {token}"

            backoff = 1.0
            while not self.stop_evt.is_set():
                try:
                    # refresh lock TTL so this runner stays active
                    try:
                        r.expire(lock_key, 30)
                    except Exception:
                        pass
                    results = r.xread({stream: last_id}, block=15000, count=50)
                except Exception as e:
                    sys.stderr.write(f"[log-forwarder] redis read error: {e}\n")
                    time.sleep(min(backoff, 5.0))
                    backoff = min(backoff * 2.0, 5.0)
                    continue

                backoff = 1.0
                if not results:
                    continue
                _, entries = results[0]
                for _id, fields in entries:
                    last_id = _id
                    try:
                        f = {k: v for k, v in fields.items()}
                        ev = format_event_from_fields(f)
                        if allow_ops and ev.get("op") not in allow_ops:
                            continue
                        self._post_json(url, headers, ev)
                    except Exception as e:
                        sys.stderr.write(f"[log-forwarder] post error: {e}\n")

    def _post_json(self, url: str, headers: dict, obj: dict):
        import json

        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        # small retry loop
        for attempt in range(1, 4):
            try:
                resp = requests.post(url, data=body, headers=headers, timeout=3)
                if 200 <= resp.status_code < 300:
                    return
                else:
                    sys.stderr.write(
                        f"[log-forwarder] HTTP {resp.status_code} on attempt {attempt}\n"
                    )
            except Exception as e:
                sys.stderr.write(f"[log-forwarder] network error attempt {attempt}: {e}\n")
            time.sleep(min(2 ** attempt, 5))


def init_log_forwarder(app: Flask):
    """Initialize and start the background log forwarder if configured.

    Config keys:
      - LOG_FORWARD_URL: destination URL (required to enable)
      - LOG_FORWARD_TOKEN: optional Bearer token
      - LOG_FORWARD_OPS: optional comma-separated op filter (e.g., "create,update")
    """
    url = app.config.get("LOG_FORWARD_URL")
    if not url:
        return
    lf = LogForwarder(app)
    lf.start()
    app.extensions["log_forwarder"] = lf
