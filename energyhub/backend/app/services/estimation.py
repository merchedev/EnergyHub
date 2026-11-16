from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from ..catalog import get_catalog_item
from ..models import Contract, Device, TariffPrice
from . import periods
from .prices import PriceCurve, PricePoint
from .tariff import period_prices


@dataclass
class DeviceEstimate:
    energy_kwh: float = 0.0
    active_kwh: float = 0.0
    standby_kwh: float = 0.0
    cost_eur: float = 0.0
    min_cost_eur: float = 0.0
    max_cost_eur: float = 0.0
    by_period: dict[str, float] = field(default_factory=lambda: {"P1": 0.0, "P2": 0.0, "P3": 0.0})
    cost_by_period: dict[str, float] = field(default_factory=lambda: {"P1": 0.0, "P2": 0.0, "P3": 0.0})
    confidence: str = "media"
    notes: list[str] = field(default_factory=list)
    hourly: dict[datetime, float] = field(default_factory=dict)

    def period_rows(self, price: TariffPrice | None) -> list[dict]:
        prices = period_prices(price) if price is not None else {p: 0.0 for p in periods.PERIOD_ORDER}
        return [
            {
                "id": p,
                "name": periods.PERIOD_NAMES[p],
                "price": prices[p],
                "energy_kwh": round(self.by_period.get(p, 0.0), 3),
                "cost_eur": round(self.cost_by_period.get(p, 0.0), 3),
            }
            for p in periods.PERIOD_ORDER
        ]


def _parse_windows(device: Device) -> list[dict]:
    raw = getattr(device, "typical_windows_json", None)
    if raw:
        try:
            value = json.loads(raw)
            if isinstance(value, list):
                windows = []
                for item in value:
                    if isinstance(item, dict) and item.get("start") and item.get("end"):
                        windows.append(
                            {
                                "start": str(item["start"]),
                                "end": str(item["end"]),
                                "weight": float(item.get("weight", 1.0) or 1.0),
                            }
                        )
                if windows:
                    return windows
        except Exception:
            pass
    catalog = get_catalog_item(device.category or "other")
    return list(catalog.get("typical_windows") or [])


def _active_hours_per_day(device: Device) -> float:
    if device.mode == "always_on":
        return 24.0
    if device.mode == "cycles":
        return max(0.0, (float(device.cycles_per_week or 0.0) / 7.0) * float(device.minutes_per_cycle or 0.0) / 60.0)
    return max(0.0, min(24.0, float(device.hours_per_day or 0.0)))


def _active_energy(device: Device, days: int) -> tuple[float, float, list[str]]:
    notes: list[str] = []
    if device.mode == "always_on":
        if device.annual_kwh is not None and device.annual_kwh > 0:
            energy = float(device.annual_kwh) / 365.0 * days
            notes.append("Consumo anual de etiqueta repartido entre los días del mes.")
            return energy, energy, notes
        duty = max(0.0, min(100.0, float(device.duty_cycle_pct or 0.0))) / 100.0
        average_w = float(device.power_active_w or 0.0) * duty + float(device.power_standby_w or 0.0) * (1 - duty)
        energy = average_w * 24.0 * days / 1000.0
        if duty < 100:
            notes.append(f"Ciclo de trabajo del {duty * 100:.0f}%.")
        return energy, 0.0, notes
    if device.mode == "cycles":
        per_cycle = device.energy_per_cycle_kwh
        if per_cycle is None or per_cycle <= 0:
            per_cycle = (
                float(device.power_active_w or 0.0)
                * float(device.minutes_per_cycle or 0.0)
                / 60.0
                / 1000.0
            )
        total_cycles = float(device.cycles_per_week or 0.0) * days / 7.0
        active = float(per_cycle) * total_cycles
        notes.append(f"{total_cycles:.1f} ciclos estimados en el mes.")
        return active, 0.0, notes
    if device.mode == "entity":
        active_hours = float(device.hours_per_day or 0.0)
        active = float(device.power_active_w or 0.0) * active_hours * days / 1000.0
        notes.append(
            "Modo entidad: el historial real de HA se usará cuando esté conectado; "
            "de momento se estima con las horas al día."
        )
        return active, 0.0, notes
    active = float(device.power_active_w or 0.0) * float(device.hours_per_day or 0.0) * days / 1000.0
    return active, 0.0, notes


def _standby_energy(device: Device, days: int, active_hours: float) -> float:
    if not bool(device.always_plugged):
        return 0.0
    standby_w = float(device.power_standby_w or 0.0)
    if standby_w <= 0:
        return 0.0
    if device.mode == "always_on":
        return 0.0
    remaining = max(0.0, 24.0 - active_hours)
    return standby_w * remaining * days / 1000.0


def _distribute_evenly(total: float, period_hours: dict[str, float]) -> dict[str, float]:
    total_hours = sum(period_hours.values()) or 1.0
    return {p: total * period_hours.get(p, 0.0) / total_hours for p in periods.PERIOD_ORDER}


def _active_by_period(
    device: Device,
    year: int,
    month: int,
    days: int,
    tz: ZoneInfo,
    country: str,
    region: str | None,
    active_total: float,
    period_hours: dict[str, float],
) -> tuple[dict[str, float], list[dict], list[str]]:
    notes: list[str] = []
    if device.mode == "always_on":
        return _distribute_evenly(active_total, period_hours), [], notes
    windows = _parse_windows(device)
    if not windows:
        windows = [{"start": "18:00", "end": "22:00", "weight": 1.0}]
        notes.append("Sin franja típica: se usa de 18:00 a 22:00 como aproximación.")
    total_weight = sum(max(0.0, float(w.get("weight", 1.0))) for w in windows) or 1.0
    result = {p: 0.0 for p in periods.PERIOD_ORDER}
    for day_offset in range(days):
        day = date(year, month, 1) + timedelta(days=day_offset)
        daily = active_total / days if days else 0.0
        for window in windows:
            share = max(0.0, float(window.get("weight", 1.0))) / total_weight
            fractions = periods.window_period_fractions(
                day,
                window["start"],
                window["end"],
                country=country,
                region=region,
                tz=tz,
            )
            for p in periods.PERIOD_ORDER:
                result[p] += daily * share * fractions.get(p, 0.0)
    notes.append(
        "Estimación con franja típica de "
        + ", ".join(f"{w['start']}–{w['end']}" for w in windows)
        + "."
    )
    return result, windows, notes


def _confidence(device: Device) -> str:
    if device.mode == "always_on":
        return "alta" if device.annual_kwh and device.annual_kwh > 0 else "media"
    if device.mode == "entity":
        return "baja"
    return "media"


def estimate_device(
    device: Device,
    contract: Contract,
    price: TariffPrice | None,
    year: int,
    month: int,
    calibration: float = 1.0,
) -> DeviceEstimate:
    try:
        tz = ZoneInfo(contract.timezone or "Europe/Madrid")
    except Exception:
        tz = ZoneInfo("Europe/Madrid")
    country = contract.country or "ES"
    region = contract.region or None
    days = periods.month_days(year, month)
    period_hours = periods.month_period_hours(year, month, tz, country=country, region=region)
    active_total, _unused, notes = _active_energy(device, days)
    active_hours = _active_hours_per_day(device)
    standby_total = _standby_energy(device, days, active_hours)
    active_by_period, windows, window_notes = _active_by_period(
        device,
        year,
        month,
        days,
        tz,
        country,
        region,
        active_total,
        period_hours,
    )
    notes.extend(window_notes)
    standby_by_period = _distribute_evenly(standby_total, period_hours)
    by_period = {p: active_by_period.get(p, 0.0) + standby_by_period.get(p, 0.0) for p in periods.PERIOD_ORDER}
    factor = max(0.0, float(calibration or 1.0))
    by_period = {p: value * factor for p, value in by_period.items()}
    active_total *= factor
    standby_total *= factor
    if price is not None:
        values = period_prices(price)
        cost_by_period = {p: by_period[p] * values[p] for p in periods.PERIOD_ORDER}
        total_cost = sum(cost_by_period.values())
        prices = [values[p] for p in periods.PERIOD_ORDER]
        if device.mode == "always_on":
            min_cost = total_cost
            max_cost = total_cost
        else:
            min_cost = sum(by_period.values()) * min(prices) if prices else 0.0
            max_cost = sum(by_period.values()) * max(prices) if prices else 0.0
    else:
        values = {p: 0.0 for p in periods.PERIOD_ORDER}
        cost_by_period = {p: 0.0 for p in periods.PERIOD_ORDER}
        total_cost = 0.0
        min_cost = 0.0
        max_cost = 0.0
        notes.append("Sin precios confirmados para este mes; el coste se mostrará cuando los configures.")
    confidence = _confidence(device)
    if factor != 1.0:
        notes.append(f"Calibrado con factura: factor {factor:.2f}.")
    return DeviceEstimate(
        energy_kwh=sum(by_period.values()),
        active_kwh=active_total,
        standby_kwh=standby_total,
        cost_eur=total_cost,
        min_cost_eur=min_cost,
        max_cost_eur=max_cost,
        by_period=by_period,
        cost_by_period=cost_by_period,
        confidence=confidence,
        notes=notes,
    )


def device_windows(device: Device) -> list[dict]:
    return _parse_windows(device)


def estimate_device_hourly(
    device: Device,
    contract: Contract,
    curve: PriceCurve,
    year: int,
    month: int,
    calibration: float = 1.0,
) -> DeviceEstimate:
    """Estimate a device by allocating its energy to each local hour."""
    try:
        tz = ZoneInfo(contract.timezone or "Europe/Madrid")
    except Exception:
        tz = ZoneInfo("Europe/Madrid")
    points = curve.points
    days = periods.month_days(year, month)
    notes: list[str] = []
    if not points:
        return DeviceEstimate(notes=["No hay precios para este mes."])
    hourly: dict[datetime, float] = {point.local_dt: 0.0 for point in points}
    active_total, _unused, active_notes = _active_energy(device, days)
    active_hours = _active_hours_per_day(device)
    standby_total = _standby_energy(device, days, active_hours)
    notes.extend(active_notes)
    factor = max(0.0, float(calibration or 1.0))
    if device.mode == "always_on":
        total = (active_total + standby_total) * factor
        per_hour = total / len(points)
        for point in points:
            hourly[point.local_dt] += per_hour
    else:
        windows = _parse_windows(device)
        if not windows:
            windows = [{"start": "18:00", "end": "22:00", "weight": 1.0}]
            notes.append("Sin franja típica: se usa de 18:00 a 22:00 como aproximación.")
        total_weight = sum(max(0.0, float(window.get("weight", 1.0))) for window in windows) or 1.0
        for day_offset in range(days):
            day = date(year, month, 1) + timedelta(days=day_offset)
            daily_active = (active_total / days) if days else 0.0
            for window in windows:
                share = max(0.0, float(window.get("weight", 1.0))) / total_weight
                energy_share = daily_active * share * factor
                fractions = periods.window_hour_fractions(
                    day, window["start"], window["end"], tz=tz
                )
                for hour_dt, fraction in fractions.items():
                    if hour_dt in hourly:
                        hourly[hour_dt] += energy_share * fraction
        if standby_total > 0:
            per_hour = standby_total * factor / len(points)
            for point in points:
                hourly[point.local_dt] += per_hour
        notes.append(
            "Estimación con franja típica de "
            + ", ".join(f"{window['start']}–{window['end']}" for window in windows)
            + "."
        )
    by_period = {p: 0.0 for p in periods.PERIOD_ORDER}
    cost_by_period = {p: 0.0 for p in periods.PERIOD_ORDER}
    price_by_hour: dict[datetime, PricePoint] = {point.local_dt: point for point in points}
    total_cost = 0.0
    for hour_dt, energy in hourly.items():
        point = price_by_hour.get(hour_dt)
        if point is None:
            continue
        by_period[point.period] += energy
        cost_by_period[point.period] += energy * point.price
        total_cost += energy * point.price
    total_energy = sum(hourly.values())
    active_scaled = active_total * factor
    standby_scaled = standby_total * factor
    if device.mode == "always_on" or total_energy <= 0:
        min_cost = max_cost = total_cost
    else:
        available_prices = [point.price for point in points if point.price > 0]
        min_cost = total_energy * min(available_prices) if available_prices else 0.0
        max_cost = total_energy * max(available_prices) if available_prices else 0.0
    confidence = _confidence(device)
    if curve.source == "ree_pvpc":
        notes.append("Coste calculado con precios PVPC horarios.")
    if factor != 1.0:
        notes.append(f"Calibrado con factura: factor {factor:.2f}.")
    return DeviceEstimate(
        energy_kwh=total_energy,
        active_kwh=active_scaled,
        standby_kwh=standby_scaled,
        cost_eur=total_cost,
        min_cost_eur=min_cost,
        max_cost_eur=max_cost,
        by_period=by_period,
        cost_by_period=cost_by_period,
        confidence=confidence,
        notes=notes,
        hourly=hourly,
    )
