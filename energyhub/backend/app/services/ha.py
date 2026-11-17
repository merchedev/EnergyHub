from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx
from websockets.asyncio.client import connect as websocket_connect

from ..config import HA_TOKEN, HA_URL, SUPERVISOR_TOKEN

ON_STATES = {"on", "open", "playing", "heat", "cool", "auto", "home", "charging"}
CONTROL_DOMAINS = {"switch", "light", "input_boolean", "fan", "climate", "media_player", "script"}
STATE_DOMAINS = CONTROL_DOMAINS | {"binary_sensor"}
SENSOR_UNITS = {"W", "kW", "kWh", "Wh", "MWh", "€/kWh", "€", "EUR"}


def is_controllable(entity_id: str | None) -> bool:
    return bool(entity_id and entity_id.split(".", 1)[0] in CONTROL_DOMAINS)


class HaError(Exception):
    pass


class HaNotConfigured(HaError):
    pass


@dataclass
class HaStatus:
    configured: bool
    connected: bool
    version: str | None = None
    location_name: str | None = None
    timezone: str | None = None
    error: str | None = None


class HaClient:
    def __init__(self) -> None:
        token = SUPERVISOR_TOKEN or HA_TOKEN
        if SUPERVISOR_TOKEN:
            base = "http://supervisor/core/api"
        elif HA_URL:
            base = HA_URL.rstrip("/")
            if not base.endswith("/api"):
                base += "/api"
        else:
            base = ""
        self.base_url = base
        self.token = token
        self.timeout = 15.0

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.token)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    @property
    def websocket_url(self) -> str:
        if SUPERVISOR_TOKEN:
            return "ws://supervisor/core/websocket"
        parsed = urlparse(self.base_url)
        scheme = "wss" if parsed.scheme == "https" else "ws"
        path = parsed.path.rstrip("/")
        return f"{scheme}://{parsed.netloc}{path}/websocket"

    async def get_statistics(
        self,
        entity_id: str,
        start: datetime,
        end: datetime,
        period: str = "hour",
    ) -> list[dict]:
        if not self.configured:
            raise HaNotConfigured("Home Assistant no está configurado")
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        if end <= start:
            return []
        request_id = 1
        try:
            async with websocket_connect(self.websocket_url, open_timeout=10, close_timeout=5) as ws:
                hello = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))
                if hello.get("type") == "auth_required":
                    await ws.send(json.dumps({"type": "auth", "access_token": self.token}))
                    auth = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))
                else:
                    auth = hello
                if auth.get("type") != "auth_ok":
                    raise HaError("Home Assistant ha rechazado la autenticación WebSocket")
                await ws.send(
                    json.dumps(
                        {
                            "id": request_id,
                            "type": "recorder/statistics_during_period",
                            "start_time": start.isoformat(),
                            "end_time": end.isoformat(),
                            "statistic_ids": [entity_id],
                            "period": period,
                            "types": ["change"],
                        }
                    )
                )
                while True:
                    message = json.loads(await asyncio.wait_for(ws.recv(), timeout=20))
                    if message.get("id") != request_id:
                        continue
                    if not message.get("success"):
                        error = message.get("error") or {}
                        raise HaError(
                            f"Home Assistant no ha devuelto estadísticas: {error.get('message', 'error desconocido')}"
                        )
                    result = message.get("result") or {}
                    rows = result.get(entity_id) if isinstance(result, dict) else None
                    return rows if isinstance(rows, list) else []
        except HaError:
            raise
        except Exception as exc:
            raise HaError(f"Error consultando estadísticas de Home Assistant: {exc}") from exc

    async def _get(self, path: str, params: dict | None = None) -> Any:
        if not self.configured:
            raise HaNotConfigured("Home Assistant no está configurado")
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}{path}",
                    headers=self._headers(),
                    params=params,
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as exc:
            raise HaError(f"Error consultando Home Assistant: {exc}") from exc

    async def get_config(self) -> dict:
        result = await self._get("/config")
        return result if isinstance(result, dict) else {}

    async def get_status(self) -> HaStatus:
        if not self.configured:
            return HaStatus(configured=False, connected=False)
        try:
            config = await self.get_config()
        except HaError as exc:
            return HaStatus(configured=True, connected=False, error=str(exc))
        return HaStatus(
            configured=True,
            connected=True,
            version=str(config.get("version") or "") or None,
            location_name=str(config.get("location_name") or "") or None,
            timezone=str(config.get("time_zone") or "") or None,
        )

    async def get_states(self) -> list[dict]:
        result = await self._get("/states")
        return result if isinstance(result, list) else []

    async def get_state(self, entity_id: str) -> dict | None:
        try:
            result = await self._get(f"/states/{entity_id}")
        except HaError:
            return None
        return result if isinstance(result, dict) else None

    async def get_history(
        self,
        entity_id: str,
        start: datetime,
        end: datetime,
    ) -> list[tuple[datetime, datetime]]:
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        data = await self._get(
            f"/history/period/{start.isoformat()}",
            params={
                "filter_entity_id": entity_id,
                "end_time": end.isoformat(),
                "minimal_response": "",
                "no_attributes": "",
            },
        )
        if not isinstance(data, list) or not data:
            return []
        states = data[0] if isinstance(data[0], list) else data
        intervals: list[tuple[datetime, datetime]] = []
        on_since: datetime | None = None
        last_time: datetime | None = None
        for item in states:
            if not isinstance(item, dict):
                continue
            timestamp = item.get("last_changed") or item.get("last_updated")
            if not timestamp:
                continue
            try:
                moment = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
            except ValueError:
                continue
            last_time = moment
            is_on = str(item.get("state", "")).lower() in ON_STATES
            if is_on and on_since is None:
                on_since = moment
            elif not is_on and on_since is not None:
                if moment > on_since:
                    intervals.append((on_since, moment))
                on_since = None
        if on_since is not None:
            intervals.append((on_since, max(end, last_time or end)))
        return intervals

    async def get_numeric_history(
        self,
        entity_id: str,
        start: datetime,
        end: datetime,
    ) -> list[tuple[datetime, float]]:
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        data = await self._get(
            f"/history/period/{start.isoformat()}",
            params={
                "filter_entity_id": entity_id,
                "end_time": end.isoformat(),
                "minimal_response": "",
                "no_attributes": "",
            },
        )
        if not isinstance(data, list) or not data:
            return []
        states = data[0] if isinstance(data[0], list) else data
        result: list[tuple[datetime, float]] = []
        for item in states:
            if not isinstance(item, dict):
                continue
            raw_state = str(item.get("state", "")).strip().lower()
            if raw_state in {"", "unknown", "unavailable", "none", "nan"}:
                continue
            try:
                value = float(raw_state)
            except ValueError:
                continue
            timestamp = item.get("last_updated") or item.get("last_changed")
            if not timestamp:
                continue
            try:
                moment = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
            except ValueError:
                continue
            result.append((moment, value))
        result.sort(key=lambda item: item[0])
        return result

    async def list_entities(self, kind: str | None = None) -> list[dict]:
        states = await self.get_states()
        result: list[dict] = []
        for state in states:
            entity_id = str(state.get("entity_id") or "")
            if not entity_id or "." not in entity_id:
                continue
            domain = entity_id.split(".", 1)[0]
            attributes = state.get("attributes") or {}
            device_class = attributes.get("device_class")
            unit = attributes.get("unit_of_measurement")
            include = False
            if kind in (None, "control") and domain in CONTROL_DOMAINS:
                include = True
            if kind == "state" and domain in STATE_DOMAINS:
                include = True
            if kind in (None, "sensor", "price", "energy", "power") and domain == "sensor":
                if kind == "price":
                    include = unit in {"€/kWh", "EUR/kWh"} or device_class == "monetary"
                elif kind == "energy":
                    include = device_class == "energy" or unit in {"kWh", "Wh", "MWh"}
                elif kind == "power":
                    include = device_class == "power" or unit in {"W", "kW"}
                else:
                    include = device_class in {"power", "energy", "monetary"} or unit in SENSOR_UNITS
            if not include:
                continue
            result.append(
                {
                    "entity_id": entity_id,
                    "name": attributes.get("friendly_name") or entity_id,
                    "domain": domain,
                    "state": str(state.get("state") or ""),
                    "unit": unit,
                    "device_class": device_class,
                    "state_class": attributes.get("state_class"),
                }
            )
        result.sort(key=lambda item: (item["domain"], item["name"].lower()))
        return result

    async def create_automation(self, automation_id: str, payload: dict) -> dict:
        if not self.configured:
            raise HaNotConfigured("Home Assistant no está configurado")
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/config/automation/config/{automation_id}",
                    headers=self._headers(),
                    json=payload,
                )
                if response.status_code >= 400:
                    raise HaError(
                        f"Home Assistant ha rechazado la automatización ({response.status_code}): {response.text[:300]}"
                    )
                try:
                    return response.json() if response.content else {"ok": True}
                except ValueError:
                    return {"ok": True}
        except httpx.HTTPError as exc:
            raise HaError(f"No se ha podido crear la automatización: {exc}") from exc

    async def delete_automation(self, automation_id: str) -> None:
        if not self.configured:
            raise HaNotConfigured("Home Assistant no está configurado")
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.delete(
                    f"{self.base_url}/config/automation/config/{automation_id}",
                    headers=self._headers(),
                )
                if response.status_code >= 400:
                    raise HaError(
                        f"Home Assistant no ha podido borrar la automatización ({response.status_code})"
                    )
        except httpx.HTTPError as exc:
            raise HaError(f"No se ha podido borrar la automatización: {exc}") from exc
