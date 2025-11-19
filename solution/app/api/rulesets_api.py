"""규칙셋 CRUD 및 탐색 API."""

from datetime import datetime, timezone

from flask import jsonify, request

from . import api_bp
from ..core import repo


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _find_ruleset(rulesets: list[dict], ruleset_id: str):
    for idx, ruleset in enumerate(rulesets):
        if ruleset.get('ruleset_id') == ruleset_id:
            return idx, ruleset
    return None, None


@api_bp.get('/rulesets')
def list_rulesets():
    """모든 룰셋을 나열합니다."""
    return jsonify(repo.load_rulesets())


@api_bp.post('/rulesets')
def create_ruleset():
    """새로운 룰셋을 등록합니다."""
    body = request.get_json(silent=True) or {}
    ruleset_id = body.get('ruleset_id')
    if not isinstance(ruleset_id, str) or not ruleset_id.strip():
        return jsonify({"error": 'ruleset_id is required'}), 400

    rulesets = repo.load_rulesets()
    if any(r.get('ruleset_id') == ruleset_id for r in rulesets):
        return jsonify({"error": 'ruleset already exists'}), 409

    now = _now_iso()
    entry = {
        **body,
        "ruleset_id": ruleset_id,
        "created_at": now,
        "updated_at": now,
    }
    rulesets.append(entry)
    repo.save_rulesets(rulesets)
    return jsonify(entry), 201


@api_bp.put('/rulesets/<ruleset_id>')
def update_ruleset(ruleset_id):
    """기존 룰셋을 수정합니다."""
    body = request.get_json(silent=True) or {}
    if 'ruleset_id' in body and body['ruleset_id'] != ruleset_id:
        return jsonify({"error": 'ruleset_id cannot be changed'}), 400

    rulesets = repo.load_rulesets()
    index, ruleset = _find_ruleset(rulesets, ruleset_id)
    if ruleset is None:
        return jsonify({"error": 'ruleset not found'}), 404

    updated = {**ruleset, **body}
    updated['updated_at'] = _now_iso()

    rulesets[index] = updated
    repo.save_rulesets(rulesets)
    return jsonify(updated)


@api_bp.delete('/rulesets/<ruleset_id>')
def delete_ruleset(ruleset_id):
    """룰셋을 삭제합니다."""
    rulesets = repo.load_rulesets()
    index, ruleset = _find_ruleset(rulesets, ruleset_id)
    if ruleset is None:
        return jsonify({"error": 'ruleset not found'}), 404

    rulesets.pop(index)
    repo.save_rulesets(rulesets)
    return jsonify({"deleted": ruleset_id})
