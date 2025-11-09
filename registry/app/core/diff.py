from __future__ import annotations


# 두 JSON(dict) 간의 간단한 차이점 계산
# - added: 새로 추가된 키와 값
# - removed: 제거된 키와 이전 값
# - changed: 값이 변경된 키와 (from, to)
def json_diff(old: dict, new: dict):
    changes = {"added": {}, "removed": {}, "changed": {}}

    def walk(o, n, prefix=""):
        o_keys = set(o.keys()) if isinstance(o, dict) else set()
        n_keys = set(n.keys()) if isinstance(n, dict) else set()

        for k in o_keys - n_keys:
            changes["removed"][f"{prefix}{k}"] = o[k]
        for k in n_keys - o_keys:
            changes["added"][f"{prefix}{k}"] = n[k]
        for k in o_keys & n_keys:
            ov = o[k]
            nv = n[k]
            if isinstance(ov, dict) and isinstance(nv, dict):
                walk(ov, nv, f"{prefix}{k}.")
            elif ov != nv:
                changes["changed"][f"{prefix}{k}"] = {"from": ov, "to": nv}

    walk(old or {}, new or {})
    return changes
