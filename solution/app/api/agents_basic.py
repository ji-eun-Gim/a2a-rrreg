from datetime import datetime, timezone

from flask import jsonify, request

from . import api_bp
from ..core import repo
from ..core.logging import append_log

_POLICY_LIST_KEYS = [
    "prompt_validation_rulesets",
    "tool_validation_rulesets",
    "response_filtering_rulesets",
]


def _ensure_list(value):
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    if isinstance(value, str):
        trimmed = value.strip()
        return [trimmed] if trimmed else []
    return []


def _normalize_policy(source, fallback=None):
    fallback = fallback or {}
    policy = {
        "enabled": bool(source.get("enabled")) if source.get("enabled") is not None else bool(fallback.get("enabled", True)),
    }
    for key in _POLICY_LIST_KEYS:
        if key in source:
            policy[key] = _ensure_list(source.get(key))
        else:
            policy[key] = _ensure_list(fallback.get(key))
    return policy


def _build_plugins(agent, card):
    plugins = agent.get("plugins")
    if isinstance(plugins, list) and plugins:
        return plugins
    skills = card.get("skills")
    if isinstance(skills, list):
        derived = []
        for skill in skills:
            if not isinstance(skill, dict):
                continue
            name = skill.get("name") or skill.get("id") or "plugin"
            derived.append(
                {
                    "name": name,
                    "type": skill.get("type") or "skill",
                    "status": skill.get("status") or "Active",
                }
            )
        if derived:
            return derived
    return []


def _normalize_agent(agent):
    if not isinstance(agent, dict):
        return agent

    card = agent.get("card") if isinstance(agent.get("card"), dict) else {}
    name = card.get("name") or agent.get("name") or "Unknown"
    description = card.get("description") or agent.get("description") or ""
    status = agent.get("status") or "Active"
    policy = _normalize_policy(agent.get("policy", {}), agent.get("policy", {}))

    normalized = {
        "agent_id": agent.get("agent_id") or name,
        "etag": agent.get("etag"),
        "versionID": agent.get("versionID"),
        "card": card,
        "status": status,
        "name": name,
        "description": description,
        "tenants": agent.get("tenants") if isinstance(agent.get("tenants"), list) else [],
        "create_ts": agent.get("create_ts"),
        "update_ts": agent.get("update_ts"),
        "created_at": agent.get("created_at") or agent.get("create_ts"),
        "updated_at": agent.get("updated_at") or agent.get("update_ts"),
        "publisher_jws": agent.get("publisher_jws"),
        "registrant": agent.get("registrant"),
        "policy": policy,
        "plugins": _build_plugins(agent, card),
    }
    return normalized


def _find_agent_index(agent_id):
    agents = repo.load_agents()
    for index, agent in enumerate(agents):
        if agent.get("agent_id") == agent_id:
            return index, agent, agents
    return None, None, agents


@api_bp.get('/agents')
def list_agents():
    """등록된 에이전트 목록을 반환."""
    agents = repo.load_agents()
    normalized = [_normalize_agent(agent) for agent in agents]
    return jsonify(normalized)


@api_bp.get('/agents/<path:agent_id>')
def get_agent(agent_id):
    """특정 에이전트 메타데이터를 반환."""
    index, agent, agents = _find_agent_index(agent_id)
    if agent is None:
        return jsonify({"error": 'agent not found'}), 404
    return jsonify(_normalize_agent(agent))


@api_bp.put('/agents/<path:agent_id>/policy')
def update_agent_policy(agent_id):
    """에이전트에 연결된 policy 룰셋을 업데이트합니다."""
    index, agent, agents = _find_agent_index(agent_id)
    if agent is None:
        return jsonify({"error": 'agent not found'}), 404

    body = request.get_json(silent=True) or {}
    existing_policy = agent.get("policy", {})
    policy = _normalize_policy(body, existing_policy)
    agent["policy"] = policy
    now = datetime.now(timezone.utc).isoformat()
    agent["update_ts"] = now
    agent["updated_at"] = now

    agents[index] = agent
    repo.save_agents(agents)
    return jsonify({"policy": policy})
