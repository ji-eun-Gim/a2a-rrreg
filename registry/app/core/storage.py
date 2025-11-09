from __future__ import annotations
from .redis_client import get_redis
from .validate import validate_agent_card
from .auditing import audit_event
from .diff import json_diff
from flask import current_app
import hashlib
import json
import time
import ulid
from urllib.parse import urlparse
import requests


AGENTS_ALL_SET = "agents:all"
NAMESPACE_INDEX = "namespace:index"


def _semver_key(version: str) -> str:
    # 버전 정렬을 위한 zero-padded 키 생성 (예: 1.2.3 -> 001.002.003)
    try:
        parts = [int(p) for p in version.split(".")]
    except Exception:
        parts = [0, 0, 0]
    while len(parts) < 3:
        parts.append(0)
    return f"{parts[0]:03d}.{parts[1]:03d}.{parts[2]:03d}"


def _extract_tags(card: dict) -> set[str]:
    # 카드 및 skills[].tags 에서 태그를 추출하여 Set으로 반환
    tags = set()
    if isinstance(card.get("tags"), list):
        tags.update([str(t) for t in card["tags"]])
    for s in card.get("skills", []) or []:
        for t in s.get("tags", []) or []:
            tags.add(str(t))
    return tags


def _now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _hash_card(card: dict) -> str:
    m = hashlib.sha256()
    m.update(json.dumps(card, sort_keys=True, ensure_ascii=False).encode("utf-8"))
    return m.hexdigest()


def create_agent(card: dict, idem_key: str | None, actor: str, ip: str) -> dict:
    # 에이전트 카드 생성: 검증은 라우터에서 처리됨
    r = get_redis()
    if idem_key:
        existing = r.get(f"idem:{idem_key}")
        if existing:
            agent = get_agent(existing)
            if agent:
                return agent
    # ULID 생성 (ulid-py)
    agent_id = str(ulid.new())
    namespace = card.get("namespace", "default")
    version = card.get("version", "0.0.0")
    sem_key = _semver_key(version)
    now = _now_iso()
    card_json = json.dumps(card, ensure_ascii=False)
    card_hash = _hash_card(card)

    key = f"agent:{agent_id}"
    owner = card.get("owner") or (actor if actor and actor != "anonymous" else "root")
    data = {
        "id": agent_id,
        "namespace": namespace,
        "version": version,
        "version_semver_key": sem_key,
        "status": "draft",
        "card_json": card_json,
        "hash_sha256": card_hash,
        "owner": owner,
        "created_at": now,
        "updated_at": now,
        "last_heartbeat": now,
    }
    r.hset(key, mapping=data)
    r.sadd(AGENTS_ALL_SET, agent_id)
    r.zadd(f"ns:{namespace}:versions", {f"{agent_id}@{version}": float(sem_key.replace(".", ""))})
    r.hset(NAMESPACE_INDEX, namespace, agent_id)

    # 태그 인덱스 업데이트
    for tag in _extract_tags(card):
        r.sadd(f"tag:{tag}", agent_id)

    if idem_key:
        r.setex(f"idem:{idem_key}", 3600, agent_id)

    audit_event("CREATE", agent_id=agent_id, namespace=namespace, actor=actor, ip=ip, status_code=201)
    r.incr(f"metrics:writes:{agent_id}")
    return data


def get_agent(agent_id: str) -> dict | None:
    r = get_redis()
    data = r.hgetall(f"agent:{agent_id}")
    if not data:
        return None
    # card_json 필드를 파싱하여 card 필드로 확장
    try:
        data["card"] = json.loads(data.get("card_json", "{}"))
    except Exception:
        data["card"] = {}
    return data


def search_agents(q: str | None, namespace: str | None, tag: str | None, status: str | None, limit: int, offset: int):
    # 간단한 필터 조합 + 문자열 포함 검색(10k 수준에서 충분)
    r = get_redis()
    ids = list(r.smembers(AGENTS_ALL_SET))
    items = []
    for aid in ids:
        a = r.hgetall(f"agent:{aid}")
        if not a:
            continue
        if namespace and a.get("namespace") != namespace:
            continue
        if status and a.get("status") != status:
            continue
        if tag and aid not in r.smembers(f"tag:{tag}"):
            continue
        if q:
            cj = a.get("card_json", "")
            if q.lower() not in cj.lower():
                continue
        # 목록 표시: 전체 카드 JSON도 포함하여 클라이언트에서 바로 확인 가능하게 함
        try:
            card = json.loads(a.get("card_json", "{}"))
            name = card.get("name")
        except Exception:
            name = None
            card = {}
        items.append(
            {
                "id": aid,
                "name": name,
                "namespace": a.get("namespace"),
                "version": a.get("version"),
                "status": a.get("status"),
                "card": card,
            }
        )
    total = len(items)
    items = items[offset : offset + limit]
    return items, total


def update_agent(agent_id: str, payload: dict, actor: str, ip: str):
    # 상태 변경 및 카드 업데이트(부분 병합, 전체 교체 모두 허용)
    r = get_redis()
    key = f"agent:{agent_id}"
    current = r.hgetall(key)
    if not current:
        return False, "not found"
    card = json.loads(current.get("card_json", "{}"))

    # 상태 변경 허용
    if "status" in payload:
        current["status"] = payload["status"]

    # 카드 전체 교체(card_json) 또는 부분 수정(card) 허용
    new_card = card.copy()
    if "card_json" in payload and isinstance(payload["card_json"], dict):
        new_card = payload["card_json"]
    elif "card" in payload and isinstance(payload["card"], dict):
        # 깊은 병합
        def merge(a, b):
            for k, v in b.items():
                if isinstance(v, dict) and isinstance(a.get(k), dict):
                    merge(a[k], v)
                else:
                    a[k] = v
        merge(new_card, payload["card"])

    # 버전 변경 시: semver 키 재계산 및 버전 인덱스 갱신
    valid, errors, _ = validate_agent_card(new_card)
    if not valid:
        return False, {"validation_errors": errors}

    diff = json_diff(card, new_card)
    if not (diff["added"] or diff["removed"] or diff["changed"]) and ("status" not in payload):
        return True, get_agent(agent_id)

    # 저장
    new_version = new_card.get("version", current.get("version"))
    if new_version != current.get("version"):
        # 버전 정렬 ZSET 갱신
        ns = current.get("namespace")
        r.zadd(f"ns:{ns}:versions", {f"{agent_id}@{new_version}": float(_semver_key(new_version).replace(".", ""))})
    current["version"] = new_version
    current["card_json"] = json.dumps(new_card, ensure_ascii=False)
    current["hash_sha256"] = _hash_card(new_card)
    current["updated_at"] = _now_iso()
    r.hset(key, mapping=current)

    # 태그 인덱스 갱신(단순화: 과거 태그는 제거하지 않음)
    for tag in _extract_tags(new_card):
        r.sadd(f"tag:{tag}", agent_id)

    r.incr(f"metrics:writes:{agent_id}")
    audit_event("UPDATE", agent_id=agent_id, namespace=current.get("namespace"), actor=actor, ip=ip, status_code=200, diff_json=diff)
    return True, get_agent(agent_id)


def retire_or_delete_agent(agent_id: str, force: bool, actor: str, ip: str):
    # 삭제 정책: 기본은 retired 상태로 전환, force=true 시 완전 삭제
    r = get_redis()
    key = f"agent:{agent_id}"
    current = r.hgetall(key)
    if not current:
        return {"error": "not found"}, 404
    if force:
        r.delete(key)
        r.srem(AGENTS_ALL_SET, agent_id)
        audit_event("DELETE", agent_id=agent_id, namespace=current.get("namespace"), actor=actor, ip=ip, status_code=204, diff_json={"status": {"from": current.get("status"), "to": "deleted"}})
        return {}, 204
    else:
        prev = current.get("status")
        current["status"] = "retired"
        current["updated_at"] = _now_iso()
        r.hset(key, mapping=current)
        audit_event("DELETE", agent_id=agent_id, namespace=current.get("namespace"), actor=actor, ip=ip, status_code=200, diff_json={"status": {"from": prev, "to": "retired"}})
        return {"status": "retired"}, 200


def import_agent_from_url(url: str, verify: dict, actor: str, ip: str):
    # URL에서 agent-card.json을 가져와 검증 후 저장 (DNS 검증은 단순 호스트 매칭 스텁)
    try:
        resp = requests.get(url, timeout=8)
    except Exception as e:
        return False, f"failed to fetch url: {e}"
    if resp.status_code != 200:
        return False, f"unexpected status: {resp.status_code}"
    try:
        card = resp.json()
    except Exception:
        return False, "response is not valid JSON"

    # Optional DNS verify (stub): ensure host matches verify.dns if present
    if verify and verify.get("dns"):
        host = urlparse(url).hostname
        if host != verify.get("dns"):
            return False, "DNS verification failed"

    valid, errors, warnings = validate_agent_card(card)
    if not valid:
        return False, {"validation_errors": errors}

    data = create_agent(card, idem_key=None, actor=actor, ip=ip)
    return True, data
