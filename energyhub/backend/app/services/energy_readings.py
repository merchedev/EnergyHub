from __future__ import annotations

import asyncio
import itertools
import json
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
    hourly: dict[datetime, float] | None = None


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


def _statistics_moment(raw: object) -> datetime | None:
    """Parse a statistics timestamp.

    Home Assistant's ``recorder/statistics_during_period`` WebSocket command
    returns ``start`` and ``end`` as Unix epoch milliseconds. Tests and older
    payloads may use ISO strings, so both formats are accepted.
    """
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        value = float(text)
    except ValueError:
        try:
            moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
        return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)
    if abs(value) > 10_000_000_000:
        value /= 1000.0
    try:
        return datetime.fromtimestamp(value, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


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


async def _statistics_data(
    client: HaClient,
    entity_id: str,
    start_local: datetime,
    end_local: datetime,
    now: datetime,
    factor: float,
    tz: ZoneInfo,
) -> tuple[float, dict[datetime, float] | None] | None:
    get_statistics = getattr(client, "get_statistics", None)
    if get_statistics is None:
        return None
    stats_end = min(end_local, now)
    if stats_end <= start_local:
        return None
    try:
        rows = await get_statistics(entity_id, start_local, stats_end, period="hour")
    except HaError:
        return None
    if not rows:
        return None
    total = 0.0
    hourly: dict[datetime, float] = {}
    has_change = False
    for row in rows:
        if not isinstance(row, dict) or row.get("change") is None:
            continue
        try:
            change = float(row["change"])
        except (TypeError, ValueError):
            continue
        total += change
        has_change = True
        moment = _statistics_moment(row.get("start"))
        if moment is None:
            continue
        local_hour = moment.astimezone(tz).replace(minute=0, second=0, microsecond=0)
        hourly[local_hour] = hourly.get(local_hour, 0.0) + change * factor
    if not has_change or total < 0:
        return None
    total_kwh = total * factor
    hourly_total = sum(hourly.values())
    if not hourly or abs(hourly_total - total_kwh) > max(0.01, total_kwh * 0.01):
        hourly = None
    return total_kwh, hourly


async def _history_hourly(
    client: HaClient,
    entity_id: str,
    start_local: datetime,
    end_local: datetime,
    now: datetime,
    factor: float,
    tz: ZoneInfo,
    current_state: dict | None,
) -> tuple[float, dict[datetime, float] | None] | None:
    end_query = min(end_local, now)
    if end_query <= start_local:
        return None
    try:
        rows = await client.get_numeric_history(entity_id, start_local, end_query)
    except HaError:
        return None
    if not rows:
        return None
    rows = list(rows)
    current_value = _numeric_state(current_state)
    if (
        current_value is not None
        and end_query >= now - timedelta(minutes=2)
        and rows[-1][0] < now - timedelta(minutes=1)
    ):
        rows.append((now, current_value))
    rows.sort(key=lambda item: item[0])
    if len(rows) < 2:
        return None
    hourly: dict[datetime, float] = {}
    total = 0.0
    for (previous_ts, previous_value), (moment, value) in itertools.pairwise(rows):
        if moment <= previous_ts:
            continue
        delta = value - previous_value
        if delta < 0:
            # Algunos contadores se reinician a diario o al desenchufar el aparato.
            # Solo aceptamos el reset si la nueva lectura es claramente un reinicio.
            if value <= max(1.0, previous_value * 0.05):
                delta = value
            else:
                return None
        if delta == 0:
            continue
        energy = delta * factor
        local_hour = moment.astimezone(tz).replace(minute=0, second=0, microsecond=0)
        hourly[local_hour] = hourly.get(local_hour, 0.0) + energy
        total += energy
    return total, hourly or None


async def fetch_month_energy(
    client: HaClient,
    contract: Contract,
    entity_id: str,
    year: int,
    month: int,
    now: datetime | None = None,
) -> EnergyReadResult:
    """Read a cumulative kWh sensor for a full month using HA statistics or history."""
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

    statistics = await _statistics_data(
        client, entity_id, start_local, end_local, now, factor, _contract_tz(contract)
    )
    if statistics is not None:
        statistics_energy, hourly = statistics
        return EnergyReadResult(
            energy_kwh=statistics_energy,
            unit=str(unit),
            hourly=hourly,
        )

    history_hourly = await _history_hourly(
        client,
        entity_id,
        start_local,
        end_local,
        now,
        factor,
        _contract_tz(contract),
        state,
    )
    if history_hourly is not None:
        history_energy, hourly = history_hourly
        return EnergyReadResult(
            energy_kwh=history_energy,
            unit=str(unit),
            hourly=hourly,
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
            error="No hay historial suficiente al inicio del mes. Revisa que la entidad conserve estadísticas en Home Assistant.",
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


def readings_for_month(db: Session, year: int, month: int) -> dict[int, DeviceEnergyReading]:
    period_start = date(year, month, 1)
    rows = db.scalars(
        select(DeviceEnergyReading).where(DeviceEnergyReading.period_start == period_start)
    ).all()
    return {row.device_id: row for row in rows}


def reading_for_device(
    db: Session, device_id: int, year: int, month: int
) -> DeviceEnergyReading | None:
    return db.scalars(
        select(DeviceEnergyReading).where(
            DeviceEnergyReading.device_id == device_id,
            DeviceEnergyReading.period_start == date(year, month, 1),
        )
    ).first()


def hourly_map(reading: DeviceEnergyReading | None) -> dict[datetime, float]:
    if reading is None or not reading.hourly_json:
        return {}
    try:
        payload = json.loads(reading.hourly_json)
    except (TypeError, ValueError):
        return {}
    if not isinstance(payload, dict):
        return {}
    result: dict[datetime, float] = {}
    for raw, value in payload.items():
        try:
            moment = datetime.fromisoformat(str(raw))
            energy = float(value)
        except (TypeError, ValueError):
            continue
        result[moment] = energy
    return result


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
            existing.hourly_json = (
                json.dumps(
                    {moment.isoformat(): value for moment, value in result.hourly.items()},
                    ensure_ascii=False,
                )
                if result.hourly
                else None
            )
            existing.fetched_at = now
            updated += 1
        db.commit()
    return updated
