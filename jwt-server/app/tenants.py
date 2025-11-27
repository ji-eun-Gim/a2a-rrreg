import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status

from .db import tenant_redis_client, redis_client
from .schemas import Tenant

router = APIRouter()

DEFAULT_TENANTS: list[Tenant] = [
    Tenant(
        id="logistics",
        name="Logistics",
        description="Logistics tenant",
    ),
    Tenant(
        id="customer-service",
        name="Customer Service",
        description="Customer support tenant",
    ),
]

DEFAULT_TENANT_RULESETS = {
    "logistics": {
        "tenant_id": "logistics",
        "description": "기본 물류 테넌트 룰셋",
        "groups": [
            {
                "id": "g_ops",
                "name": "물류 운영",
                "description": "운영/배송 담당 그룹",
                "members": ["dev1@a2a.com", "lead@a2a.com"],
            },
            {
                "id": "g_finance",
                "name": "정산",
                "description": "물류 정산/회계",
                "members": ["cfo@a2a.com"],
            },
        ],
        "access_controls": [
            {
                "ruleset_id": "logistics_tool_block",
                "group_id": "g_ops",
                "type": "tool_validation",
                "target_agent": "agent_researcher",
                "tool_name": "google_search",
                "enabled": True,
                "rules": {"action": "deny"},
                "description": "운영팀의 외부 검색 차단",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        ],
    },
    "customer-service": {
        "tenant_id": "customer-service",
        "description": "기본 고객센터 테넌트 룰셋",
        "groups": [
            {
                "id": "g_cs",
                "name": "CS 팀",
                "description": "고객 문의 대응",
                "members": ["cs1@a2a.com", "cs2@a2a.com"],
            }
        ],
        "access_controls": [
            {
                "ruleset_id": "cs_prompt_validation",
                "group_id": "g_cs",
                "type": "prompt_validation",
                "enabled": True,
                "rules": {
                    "blocked_keywords": ["refund all", "full export", "delete db"]
                },
                "description": "과도한 프롬프트 요청 제한",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        ],
    },
}


def _tenant_key(tenant_id: str) -> str:
    return f"tenant:{tenant_id}"


def _ruleset_key(tenant_id: str) -> str:
    return f"tenant:{tenant_id}:rulesets"


def _load_ruleset_payload(tenant_id: str) -> dict:
    raw = tenant_redis_client.get(_ruleset_key(tenant_id))
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tenant rulesets not found"
        )
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Corrupted ruleset data",
        )


def _save_ruleset_payload(tenant_id: str, payload: dict) -> None:
    tenant_redis_client.set(
        _ruleset_key(tenant_id), json.dumps(payload, ensure_ascii=False)
    )


def _normalize_user_tenants(raw) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(x) for x in raw if isinstance(x, str)]
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return [str(x) for x in data if isinstance(x, str)]
        except json.JSONDecodeError:
            return [raw] if raw else []
        return [raw] if raw else []
    return []


def _ensure_user_has_tenant(email: str, tenant_id: str):
    """유저 해시가 있을 때 tenant 필드에 tenant_id를 추가한다."""
    key = f"user:{email}"
    data = redis_client.hgetall(key)
    if not data:
        return

    tenants = _normalize_user_tenants(data.get("tenant"))
    if tenant_id not in tenants:
        tenants.append(tenant_id)
        redis_client.hset(key, mapping={"tenant": json.dumps(tenants)})


def _as_bool(value, default=True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return default


def _load_or_init_ruleset_payload(tenant_id: str) -> dict:
    try:
        return _load_ruleset_payload(tenant_id)
    except HTTPException as exc:  # noqa: PERF203 - clarity
        if exc.status_code != status.HTTP_404_NOT_FOUND:
            raise
        return {
            "tenant_id": tenant_id,
            "description": "",
            "groups": [],
            "access_controls": [],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }


def _normalize_access_control(payload: dict, existing: dict | None = None) -> dict:
    existing = existing or {}
    merged = {**existing, **(payload or {})}
    normalized = {
        **merged,
        "ruleset_id": merged.get("ruleset_id") or existing.get("ruleset_id"),
        "group_id": merged.get("group_id") or existing.get("group_id"),
        "type": merged.get("type") or existing.get("type") or "tool_validation",
        "target_agent": merged.get("target_agent")
        or merged.get("agent_id")
        or existing.get("target_agent"),
        "tool_name": merged.get("tool_name")
        or merged.get("tool")
        or existing.get("tool_name"),
        "rules": merged.get("rules") or existing.get("rules") or {},
        "enabled": _as_bool(
            merged.get("enabled")
            if "enabled" in merged
            else None,
            default=_as_bool(existing.get("enabled"), True),
        ),
        "description": merged.get("description") or existing.get("description") or "",
        "name": merged.get("name")
        or existing.get("name")
        or merged.get("ruleset_id")
        or existing.get("ruleset_id"),
    }
    return normalized


def _find_access_control_index(data: dict, ruleset_id: str) -> tuple[int | None, dict | None]:
    access_controls = data.get("access_controls") or []
    for idx, item in enumerate(access_controls):
        if item.get("ruleset_id") == ruleset_id:
            return idx, item
    return None, None


def _seed_default_tenants() -> None:
    for tenant in DEFAULT_TENANTS:
        key = _tenant_key(tenant.id)
        if tenant_redis_client.exists(key):
            continue
        tenant_redis_client.hset(
            key,
            mapping={
                "id": tenant.id,
                "name": tenant.name,
                "description": tenant.description or "",
            },
        )


def _seed_default_rulesets() -> None:
    for tenant_id, payload in DEFAULT_TENANT_RULESETS.items():
        key = _ruleset_key(tenant_id)
        if tenant_redis_client.exists(key):
            continue
        tenant_redis_client.set(key, json.dumps(payload, ensure_ascii=False))


def _load_tenant(key: str) -> Tenant:
    data = tenant_redis_client.hgetall(key)
    return Tenant(
        id=data.get("id") or key.split("tenant:", 1)[-1],
        name=data.get("name") or "",
        description=data.get("description") or None,
    )


@router.get("/tenants", response_model=list[Tenant])
def list_tenants():
    keys = tenant_redis_client.keys("tenant:*")
    tenants: list[Tenant] = []
    for key in keys:
        # skip ruleset payload keys (string type)
        if key.endswith(":rulesets"):
            continue
        if tenant_redis_client.type(key) != "hash":
            continue
        tenants.append(_load_tenant(key))
    return tenants


@router.post("/tenants", response_model=Tenant, status_code=status.HTTP_201_CREATED)
def create_tenant(tenant: Tenant):
    key = _tenant_key(tenant.id)
    if tenant_redis_client.exists(key):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Tenant already exists",
        )

    tenant_redis_client.hset(
        key,
        mapping={
            "id": tenant.id,
            "name": tenant.name,
            "description": tenant.description or "",
        },
    )
    # 신규 테넌트 룰셋 payload 기본 생성
    if not tenant_redis_client.exists(_ruleset_key(tenant.id)):
        _save_ruleset_payload(
            tenant.id,
            {
                "tenant_id": tenant.id,
                "description": tenant.description or "",
                "groups": [],
                "access_controls": [],
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
    return tenant


@router.get("/tenants/{tenant_id}/rulesets")
def get_tenant_rulesets(tenant_id: str):
    tenant_id = tenant_id.strip().lower()
    return _load_ruleset_payload(tenant_id)


@router.post(
    "/tenants/{tenant_id}/access-controls",
    status_code=status.HTTP_201_CREATED,
)
def create_access_control(tenant_id: str, payload: dict):
    """그룹 단위 access control 룰셋을 추가한다."""
    tenant_id = tenant_id.strip().lower()
    ruleset_id = (payload.get("ruleset_id") or "").strip()
    group_id = (payload.get("group_id") or "").strip()
    if not ruleset_id or not group_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ruleset_id and group_id are required",
        )

    data = _load_or_init_ruleset_payload(tenant_id)
    groups = data.get("groups") or []
    if groups and not any(g.get("id") == group_id for g in groups):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="group not found"
        )

    access_controls = data.get("access_controls") or []
    if any(item.get("ruleset_id") == ruleset_id for item in access_controls):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="ruleset already exists"
        )

    normalized = _normalize_access_control(payload)
    normalized["ruleset_id"] = ruleset_id
    normalized["group_id"] = group_id
    normalized["created_at"] = normalized.get("created_at") or datetime.now(timezone.utc).isoformat()
    normalized["updated_at"] = datetime.now(timezone.utc).isoformat()

    access_controls.append(normalized)
    data["access_controls"] = access_controls
    data["updated_at"] = normalized["updated_at"]
    _save_ruleset_payload(tenant_id, data)
    return normalized


@router.put("/tenants/{tenant_id}/access-controls/{ruleset_id}")
def update_access_control(tenant_id: str, ruleset_id: str, payload: dict):
    """기존 access control 룰셋을 수정한다."""
    tenant_id = tenant_id.strip().lower()
    ruleset_id = ruleset_id.strip()

    data = _load_ruleset_payload(tenant_id)
    idx, existing = _find_access_control_index(data, ruleset_id)
    if existing is None or idx is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="ruleset not found"
        )

    if "group_id" in payload:
        new_group_id = (payload.get("group_id") or "").strip()
        if new_group_id and not any(
            g.get("id") == new_group_id for g in data.get("groups") or []
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="group not found"
            )

    normalized = _normalize_access_control(payload, existing=existing)
    normalized["ruleset_id"] = ruleset_id
    normalized["group_id"] = (
        normalized.get("group_id") or existing.get("group_id") or ""
    )
    normalized["created_at"] = existing.get("created_at") or existing.get("updated_at")
    normalized["updated_at"] = datetime.now(timezone.utc).isoformat()

    access_controls = data.get("access_controls") or []
    access_controls[idx] = normalized
    data["access_controls"] = access_controls
    data["updated_at"] = normalized["updated_at"]
    _save_ruleset_payload(tenant_id, data)
    return normalized


@router.delete("/tenants/{tenant_id}/access-controls/{ruleset_id}")
def delete_access_control(tenant_id: str, ruleset_id: str):
    """access control 룰셋을 삭제한다."""
    tenant_id = tenant_id.strip().lower()
    ruleset_id = ruleset_id.strip()

    data = _load_ruleset_payload(tenant_id)
    access_controls = data.get("access_controls") or []
    if not any(item.get("ruleset_id") == ruleset_id for item in access_controls):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="ruleset not found"
        )

    data["access_controls"] = [
        item for item in access_controls if item.get("ruleset_id") != ruleset_id
    ]
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_ruleset_payload(tenant_id, data)
    return {"deleted": ruleset_id}


@router.post(
    "/tenants/{tenant_id}/groups",
    status_code=status.HTTP_201_CREATED,
)
def create_group(tenant_id: str, payload: dict):
    """테넌트에 새 그룹을 추가한다."""
    tenant_id = tenant_id.strip().lower()
    group_id = (payload.get("id") or "").strip()
    name = (payload.get("name") or group_id).strip()
    description = payload.get("description") or ""

    if not group_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="group id is required"
        )

    try:
        data = _load_ruleset_payload(tenant_id)
    except HTTPException:
        data = {
            "tenant_id": tenant_id,
            "description": "",
            "groups": [],
            "access_controls": [],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    groups = data.get("groups") or []
    if any(g.get("id") == group_id for g in groups):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="group already exists"
        )

    new_group = {
        "id": group_id,
        "name": name or group_id,
        "description": description,
        "members": [],
        "tenant_id": tenant_id,
    }
    groups.append(new_group)
    data["groups"] = groups
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_ruleset_payload(tenant_id, data)
    return new_group


@router.put(
    "/tenants/{tenant_id}/groups/{group_id}/members",
    status_code=status.HTTP_200_OK,
)
def update_group_members(tenant_id: str, group_id: str, payload: dict):
    """그룹 멤버 목록을 통째로 교체한다."""
    tenant_id = tenant_id.strip().lower()
    group_id = group_id.strip()
    members = payload.get("members")
    if not isinstance(members, list) or any(not isinstance(m, str) for m in members):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="members must be an array of email strings",
        )

    data = _load_ruleset_payload(tenant_id)
    groups = data.get("groups") or []
    target = next((g for g in groups if g.get("id") == group_id), None)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found",
        )

    target["members"] = members
    data["groups"] = groups
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_ruleset_payload(tenant_id, data)

    # user DB에도 tenant 정보 추가
    for email in members:
        _ensure_user_has_tenant(email, tenant_id)

    return {"group_id": group_id, "members": members}


@router.put("/tenants/{tenant_id}/groups/{group_id}")
def update_group(tenant_id: str, group_id: str, payload: dict):
    """그룹의 메타데이터(이름, 설명)를 수정한다."""
    tenant_id = tenant_id.strip().lower()
    group_id = group_id.strip()
    name = (payload.get("name") or "").strip()
    description = payload.get("description") or ""

    data = _load_ruleset_payload(tenant_id)
    groups = data.get("groups") or []
    target = next((g for g in groups if g.get("id") == group_id), None)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found",
        )

    if name:
        target["name"] = name
    target["description"] = description
    data["groups"] = groups
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_ruleset_payload(tenant_id, data)
    return target


@router.delete("/tenants/{tenant_id}/groups/{group_id}")
def delete_group(tenant_id: str, group_id: str):
    """그룹을 삭제하고 해당 group_id를 참조하는 access_controls도 제거한다."""
    tenant_id = tenant_id.strip().lower()
    group_id = group_id.strip()

    data = _load_ruleset_payload(tenant_id)
    groups = data.get("groups") or []
    if not any(g.get("id") == group_id for g in groups):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found",
        )
    data["groups"] = [g for g in groups if g.get("id") != group_id]

    ac = data.get("access_controls") or []
    data["access_controls"] = [
        item for item in ac if item.get("group_id") != group_id
    ]
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_ruleset_payload(tenant_id, data)
    return {"deleted": group_id}


@router.delete("/tenants/{tenant_id}")
def delete_tenant(tenant_id: str):
    """테넌트 해시와 룰셋 payload를 함께 삭제한다."""
    tenant_id = tenant_id.strip().lower()
    tkey = _tenant_key(tenant_id)
    rkey = _ruleset_key(tenant_id)

    existed = tenant_redis_client.exists(tkey) or tenant_redis_client.exists(rkey)
    if not existed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    tenant_redis_client.delete(tkey)
    tenant_redis_client.delete(rkey)
    return {"deleted": tenant_id}


_seed_default_tenants()
_seed_default_rulesets()
