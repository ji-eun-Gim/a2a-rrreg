import json
from app import create_app


def test_validate_valid_card(client):
    card = {
        "name": "Test Agent",
        "version": "1.0.0",
        "protocolVersion": "1",
        "url": "https://example.com",
        "skills": [{"id": "s1", "name": "Skill1", "description": "desc"}],
    }
    rv = client.post("/v1/agents:validate", json=card)
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["valid"] is True
    assert "warnings" in data


def test_validate_invalid_card(client):
    card = {"name": "X"}
    rv = client.post("/v1/agents:validate", json=card)
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["valid"] is False
    assert len(data["errors"]) > 0

