from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Contract, Device, DeviceEnergyReading
from .ha import HaClient, HaError

LOGGER = logging.getLogger(__name__)
CURRENT_REFRESH_INTERVAL = timedelta(minutes=15)
PREVIEW_CACHE_INTERVAL = timedelta(minutes=3)
ENERGY_UNITS = {"kWh": 1.0, "Wh": 0.001, "MWh": 1000.0}

_refresh_lock = asyncio.Lock()
_preview_cache: dict[tuple[str, str], tuple[datetime, EnergyReadResult]] = {}


class EnergyReadError(Exception):
    pass


@dataclass
class EnergyReadResult:
    energy_kwh: float | None
    start_value: float | None = None
    end_value: float | None = None
    unit: str | None = None
    error: str | None = None


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _contract_tz(contract: Contract) -> ZoneInfo:
    try:
        return ZoneInfo(contract.timezone or "Europe/Madrid")
    except Exception:
        return ZoneInfo("Europe/Madrid")


def _month_bounds(contract: Contract, year: int, month: int) -> tuple[datetime, datetime]:
    tz = _contract_tz(contract)
    start = datetime(year, month, 1, tzinfo=tz)
    end = datetime(year + 1, 1, 1, tzinfo=tz) if month == 12 else datetime(year, month + 1, 1, tzinfo=tz)
    return start, end


def _numeric_state(state: dict | None) -> float | None:
    if not isinstance(state, dict):
        return None
    raw = str(state.get("state", "")).strip().lower()
    if raw in {"", "unknown", "unavailable", "none", "nan"}:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _unit_factor(unit: str | None) -> float | None:
    return ENERGY_UNITS.get((unit or "").strip())


async def _reading_near(
    client: HaClient,
    entity_id: str,
    moment: datetime,
    window: timedelta = timedelta(hours=36),
) -> float | None:
    """Return the last numeric reading at or before moment, or the next one."""
    try:
        rows = await client.get_numeric_history(entity_id, moment - window, moment + window)
    except HaError:
        return None
    if not rows:
        return None
    before = [value for timestamp, value in rows if timestamp <= moment]
    if before:
        return before[-1]
    after = [value for timestamp, value in rows if timestamp > moment]
    return after[0] if after else None


async def fetch_month_energy(
    client: HaClient,
    contract: Contract,
    entity_id: str,
    year: int,
    month: int,
    now: datetime | None = None,
) -> EnergyReadResult:
    """Read a cumulative kWh sensor for a full month using HA history."""
    now = now or datetime.now(timezone.utc)
    start_local, end_local = _month_bounds(contract, year, month)
    if start_local.astimezone(timezone.utc) > now:
        return EnergyReadResult(None, error="El mes todavía no ha empezado.")

    state = await client.get_state(entity_id)
    if state is None:
        return EnergyReadResult(None, error="La entidad no existe o no está disponible en Home Assistant.")
    attributes = state.get("attributes") or {}
    unit = attributes.get("unit_of_measurement")
    factor = _unit_factor(str(unit) if unit else None)
    if factor is None:
        return EnergyReadResult(None, unit=str(unit) if unit else None, error="La entidad no usa kWh, Wh o MWh.")

    state_class = str(attributes.get("state_class") or "")
    if state_class == "measurement":
        return EnergyReadResult(
            None,
            unit=str(unit),
            error="La entidad parece una medición instantánea, no un contador acumulado.",
        )

    end_is_current = end_local.astimezone(timezone.utc) > now - timedelta(minutes=2)
    end_value = _numeric_state(state) if end_is_current else await _reading_near(client, entity_id, end_local)
    if end_value is None:
        return EnergyReadResult(None, unit=str(unit), error="No hay una lectura final válida para el mes.")
    start_value = await _reading_near(client, entity_id, start_local)
    if start_value is None:
        return EnergyReadResult(
            None,
            end_value=end_value,
            unit=str(unit),
            error="No hay una lectura inicial válida para el mes.",
        )

    energy_kwh = (end_value - start_value) * factor
    if energy_kwh < 0:
        return EnergyReadResult(
            None,
            start_value=start_value,
            end_value=end_value,
            unit=str(unit),
            error="La lectura final es menor que la inicial; puede haber un reinicio del contador.",
        )
    return EnergyReadResult(
        energy_kwh=energy_kwh,
        start_value=start_value,
        end_value=end_value,
        unit=str(unit),
    )


async def cached_month_energy(
    client: HaClient,
    contract: Contract,
    entity_id: str,
    year: int,
    month: int,
    now: datetime | None = None,
) -> EnergyReadResult:
    now = now or datetime.now(timezone.utc)
    key = (entity_id, f"{year:04d}-{month:02d}")
    cached = _preview_cache.get(key)
    if cached is not None:
        fetched_at, result = cached
        if now - fetched_at < PREVIEW_CACHE_INTERVAL:
            return result
    result = await fetch_month_energy(client, contract, entity_id, year, month, now=now)
    _preview_cache[key] = (now, result)
    return result


def readings_for_month(db: Session, year: int, month: int) -> dict[int, float]:
    period_start = date(year, month, 1)
    rows = db.scalars(
        select(DeviceEnergyReading).where(DeviceEnergyReading.period_start == period_start)
    ).all()
    return {row.device_id: row.energy_kwh for row in rows}


def reading_for_device(db: Session, device_id: int, year: int, month: int) -> float | None:
    row = db.scalars(
        select(DeviceEnergyReading).where(
            DeviceEnergyReading.device_id == device_id,
            DeviceEnergyReading.period_start == date(year, month, 1),
        )
    ).first()
    return row.energy_kwh if row is not None else None


def _needs_refresh(
    existing: DeviceEnergyReading | None,
    period_start: date,
    end_local: datetime,
    now: datetime,
    current_start: date,
    force: bool,
) -> bool:
    if force or existing is None:
        return True
    fetched_at = _as_utc(existing.fetched_at)
    if fetched_at is None:
        return True
    if period_start == current_start:
        return now - fetched_at >= CURRENT_REFRESH_INTERVAL
    # Un mes pasado solo se vuelve a leer si la última lectura se hizo antes de terminar.
    return fetched_at < end_local.astimezone(timezone.utc)


async def refresh_readings(
    db: Session,
    client: HaClient,
    contract: Contract,
    devices: list[Device],
    year: int,
    month: int,
    force: bool = False,
) -> int:
    if not client.configured:
        return 0
    devices = [device for device in devices if device.mode == "entity" and device.energy_entity_id]
    if not devices:
        return 0

    _, end_local = _month_bounds(contract, year, month)
    tz = _contract_tz(contract)
    now = datetime.now(timezone.utc)
    current_start = date(datetime.now(tz).year, datetime.now(tz).month, 1)
    updated = 0

    async with _refresh_lock:
        for device in devices:
            period_start = date(year, month, 1)
            existing = db.scalars(
                select(DeviceEnergyReading).where(
                    DeviceEnergyReading.device_id == device.id,
                    DeviceEnergyReading.period_start == period_start,
                )
            ).first()
            if not _needs_refresh(existing, period_start, end_local, now, current_start, force):
                continue
            try:
                result = await cached_month_energy(
                    client, contract, str(device.energy_entity_id), year, month, now=now
                )
            except HaError as exc:
                LOGGER.warning("No se pudo leer la energía de %s: %s", device.energy_entity_id, exc)
                continue
            if result.error is not None or result.energy_kwh is None:
                if result.error:
                    LOGGER.info("Lectura de energía no válida para %s: %s", device.energy_entity_id, result.error)
                continue
            if existing is None:
                existing = DeviceEnergyReading(
                    device_id=device.id,
                    period_start=period_start,
                    energy_kwh=result.energy_kwh,
                    source="ha_energy_sensor",
                )
                db.add(existing)
            existing.energy_kwh = result.energy_kwh
            existing.source = "ha_energy_sensor"
            existing.start_value = result.start_value
            existing.end_value = result.end_value
            existing.unit = result.unit
            existing.fetched_at = now
            updated += 1
        db.commit()
    return updated
