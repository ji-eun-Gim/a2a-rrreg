import json
import pytest
from app import create_app


@pytest.fixture()
def app_instance():
    app = create_app({
        "TESTING": True,
        "REGISTRY_API_TOKEN": "testtoken",
    })
    yield app


@pytest.fixture()
def client(app_instance):
    return app_instance.test_client()


VALID_CARD = {
    "name": "My Agent",
    "version": "1.2.3",
    "protocolVersion": "1",
    "url": "https://example.com",
    "skills": [{"id": "s1", "name": "s1", "description": "desc"}],
}


def test_create_read_and_audit(client, app_instance):
    rv = client.post("/v1/agents", json=VALID_CARD, headers={"Authorization": "Bearer testtoken", "Idempotency-Key": "abc"})
    assert rv.status_code == 201
    aid = rv.get_json()["id"]

    rv2 = client.get(f"/v1/agents/{aid}")
    assert rv2.status_code == 200
    data = rv2.get_json()
    assert data["id"] == aid

    # audit: read events should exist
    rv3 = client.get("/v1/audit")
    assert rv3.status_code == 200
    items = rv3.get_json()["items"]
    assert any(i.get("event") == "READ" and i.get("agent_id") == aid for i in items)


def test_update_and_diff(client):
    rv = client.post("/v1/agents", json=VALID_CARD, headers={"Authorization": "Bearer testtoken"})
    aid = rv.get_json()["id"]
    rv2 = client.patch(f"/v1/agents/{aid}", json={"card": {"name": "My Agent 2"}}, headers={"Authorization": "Bearer testtoken"})
    assert rv2.status_code == 200

    # audit update present
    rv3 = client.get("/v1/audit")
    items = rv3.get_json()["items"]
    assert any(i.get("event") == "UPDATE" and i.get("agent_id") == aid for i in items)


def test_delete_retire(client):
    rv = client.post("/v1/agents", json=VALID_CARD, headers={"Authorization": "Bearer testtoken"})
    aid = rv.get_json()["id"]
    rv2 = client.delete(f"/v1/agents/{aid}", headers={"Authorization": "Bearer testtoken"})
    assert rv2.status_code == 200
    assert rv2.get_json()["status"] == "retired"
