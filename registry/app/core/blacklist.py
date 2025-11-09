from __future__ import annotations
import os
from urllib.parse import urlparse
from flask import current_app


def _normalize_url(u: str) -> str:
    s = (u or "").strip().lower()
    if s.endswith("/"):
        s = s[:-1]
    return s


def _host_from_url(u: str) -> str | None:
    try:
        if "://" in u:
            p = urlparse(u)
            return (p.hostname or "").lower()
        # treat as host[/path]
        h = u.split("/", 1)[0]
        return h.lower()
    except Exception:
        return None


def _load_blacklist(app) -> tuple[set[str], set[str]]:
    # Returns (exact_urls, hosts)
    if not hasattr(app, "extensions"):
        app.extensions = {}
    cached = app.extensions.get("malicious_blacklist")
    if cached is not None:
        return cached
    # Default path inside package
    base_dir = os.path.dirname(os.path.dirname(__file__))  # app/
    path = app.config.get("BLACKLIST_PATH") or os.path.join(base_dir, "data", "malicious_urls.txt")
    exact_urls: set[str] = set()
    hosts: set[str] = set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if not s or s.startswith("#"):
                    continue
                exact = _normalize_url(s)
                exact_urls.add(exact)
                h = _host_from_url(s)
                if h:
                    hosts.add(h)
    except Exception:
        # If file missing, keep empty sets
        pass
    app.extensions["malicious_blacklist"] = (exact_urls, hosts)
    return exact_urls, hosts


def is_url_blacklisted(url: str) -> tuple[bool, dict]:
    """Check whether the given URL is blacklisted.

    Returns (blocked, meta)
    meta example: {"reason": "host_match|exact_match", "match": "..."}
    """
    app = current_app
    exact_urls, hosts = _load_blacklist(app)
    u_norm = _normalize_url(url)
    if u_norm in exact_urls:
        return True, {"reason": "exact_match", "match": u_norm}
    host = _host_from_url(url) or ""
    if host and host in hosts:
        return True, {"reason": "host_match", "match": host}
    return False, {}

