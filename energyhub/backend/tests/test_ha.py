from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.main import app
from app.routers import api as api_module
from app.services import ha
from app.services import ha as ha_module


async def test_get_areas_reads_the_websocket_area_registry(monkeypatch) -> None:
    sent: list[dict] = []

    class FakeWebSocket:
        def __init__(self) -> None:
            self.messages = [
                json.dumps({"type": "auth_required"}),
                json.dumps({"type": "auth_ok"}),
                json.dumps(
                    {
                        "id": 1,
                        "success": True,
                        "result": [{"area_id": "cocina", "name": "Cocina", "icon": None, "floor_id": None}],
                    }
                ),
            ]

        async def recv(self) -> str:
            return self.messages.pop(0)

        async def send(self, data: str) -> None:
            sent.append(json.loads(data))

    class FakeConnect:
        async def __aenter__(self) -> FakeWebSocket:
            return FakeWebSocket()

        async def __aexit__(self, *_args) -> bool:
            return False

    monkeypatch.setattr(ha_module, "websocket_connect", lambda *_args, **_kwargs: FakeConnect())
    client = ha.HaClient()
    monkeypatch.setattr(client, "base_url", "http://test")
    monkeypatch.setattr(client, "token", "test")
    areas = await client.get_areas()
    assert areas == [{"id": "cocina", "name": "Cocina", "icon": None, "floor_id": None}]
    assert sent[0] == {"type": "auth", "access_token": "test"}
    assert sent[1] == {"id": 1, "type": "config/area_registry/list"}


async def test_get_areas_sorts_and_ignores_invalid_entries(monkeypatch) -> None:
    client = ha.HaClient()

    async def fake_ws_command(payload: dict, **_kwargs):
        assert payload["type"] == "config/area_registry/list"
        return [
            {"area_id": "salon", "name": "Salón", "icon": "mdi:television", "floor_id": "planta_baja"},
            {"area_id": "cocina", "name": "Cocina", "icon": None, "floor_id": None},
            {"area_id": "", "name": "Sin id"},
            {"area_id": "sin_nombre", "name": ""},
            "no es un dict",
        ]

    monkeypatch.setattr(client, "_ws_command", fake_ws_command)
    areas = await client.get_areas()
    assert [area["name"] for area in areas] == ["Cocina", "Salón"]
    assert areas[0]["id"] == "cocina"
    assert areas[1]["icon"] == "mdi:television"


def test_ha_areas_endpoint_returns_registry(monkeypatch) -> None:
    async def fake_get_areas():
        return [{"id": "cocina", "name": "Cocina", "icon": "mdi:fridge", "floor_id": "planta_baja"}]

    monkeypatch.setattr(api_module.ha_client, "base_url", "http://test")
    monkeypatch.setattr(api_module.ha_client, "token", "test")
    monkeypatch.setattr(api_module.ha_client, "get_areas", fake_get_areas)
    with TestClient(app) as client:
        response = client.get("/api/ha/areas")
    assert response.status_code == 200
    data = response.json()
    assert data["configured"] is True
    assert data["items"] == [
        {"id": "cocina", "name": "Cocina", "icon": "mdi:fridge", "floor_id": "planta_baja"}
    ]


def test_ha_areas_endpoint_without_home_assistant(monkeypatch) -> None:
    monkeypatch.setattr(api_module.ha_client, "base_url", "")
    monkeypatch.setattr(api_module.ha_client, "token", "")
    with TestClient(app) as client:
        response = client.get("/api/ha/areas")
    assert response.status_code == 200
    assert response.json() == {"configured": False, "items": []}
