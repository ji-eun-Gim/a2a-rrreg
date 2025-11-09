import hashlib
import json


def compute_etag(obj) -> str:
    try:
        body = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    except Exception:
        body = str(obj)
    h = hashlib.sha256(body.encode("utf-8"))
    # Use weak ETag format to avoid strict byte-for-byte constraints
    return 'W/"' + h.hexdigest() + '"'

