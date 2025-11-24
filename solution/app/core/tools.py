"""Utility script to inspect agent tools from the local agent DB."""
from __future__ import annotations

from typing import List, Dict, Any

from . import repo


def _extract_tool_ids(agent: Dict[str, Any]) -> List[str]:
    """Pull tool_id values from agent.card.extensions[*].params.tools."""
    card = agent.get("card") if isinstance(agent, dict) else {}
    extensions = card.get("extensions")
    if not isinstance(extensions, list):
        return []

    tool_ids: list[str] = []
    for ext in extensions:
        params = ext.get("params") if isinstance(ext, dict) else None
        tools = params.get("tools") if isinstance(params, dict) else None
        if not isinstance(tools, list):
            continue
        for tool in tools:
            tid = tool.get("tool_id") if isinstance(tool, dict) else None
            if isinstance(tid, str) and tid:
                tool_ids.append(tid)
    return tool_ids


def main() -> None:
    agents = repo.load_agents()
    if not agents:
        print("No agents found.")
        return

    print("Agents:")
    for idx, agent in enumerate(agents, 1):
        aid = agent.get("agent_id") or "(unknown id)"
        name = (agent.get("card") or {}).get("name") or agent.get("name") or aid
        print(f"[{idx}] {name} ({aid})")

    try:
        choice = int(input("Select agent number: ").strip())
    except Exception:
        print("Invalid selection.")
        return

    if choice < 1 or choice > len(agents):
        print("Selection out of range.")
        return

    agent = agents[choice - 1]
    tool_ids = _extract_tool_ids(agent)
    aid = agent.get("agent_id") or "(unknown id)"
    print(f"tool_id list for {aid}:")
    if not tool_ids:
        print("  (no tools found)")
        return
    for tid in tool_ids:
        print(f"  - {tid}")


if __name__ == "__main__":
    main()
