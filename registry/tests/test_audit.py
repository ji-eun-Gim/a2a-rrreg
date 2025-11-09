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


def test_audit_stream_records_reads(client):
    card = {
        "name": "A",
        "version": "0.1.0",
        "protocolVersion": "1",
        "url": "https://example.com",
        "skills": [{"id": "s1", "name": "s", "description": "d"}],
    }
    rv = client.post("/v1/agents", json=card, headers={"Authorization": "Bearer testtoken"})
    aid = rv.get_json()["id"]

    client.get(f"/v1/agents/{aid}")

    rv2 = client.get(f"/v1/audit?agent_id={aid}&event=READ")
    assert rv2.status_code == 200
    items = rv2.get_json()["items"]
    assert len(items) >= 1
