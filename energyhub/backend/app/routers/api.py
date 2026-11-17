from __future__ import annotations

import json
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..catalog import CATALOG, get_catalog_item
from ..config import APP_VERSION
from ..database import get_db
from ..models import (
    AutomationLog,
    Calibration,
    Contract,
    Device,
    PriceProposal,
    Recommendation,
    Setting,
    TariffPrice,
)
from ..schemas import (
    CalibrationIn,
    CalibrationOut,
    ContractIn,
    ContractOut,
    DeviceIn,
    DeviceOut,
    DevicePreviewIn,
    ManualPriceIn,
    PriceProposalOut,
    SettingsUpdate,
)
from ..services import (
    changelog,
    demo,
    energy_readings,
    estimation,
    ha,
    pepe,
    periods,
    prices,
    profiles,
    pvpc,
    recommendations,
    tariff,
)

router = APIRouter(prefix="/api")
ha_client = ha.HaClient()


def _contract_or_404(db: Session) -> Contract:
    contract = tariff.get_active_contract(db)
    if contract is None:
        raise HTTPException(status_code=404, detail="No hay ningún contrato configurado")
    return contract


def _get_setting(db: Session, key: str, default: str = "") -> str:
    item = db.get(Setting, key)
    return item.value if item is not None else default


def _set_setting(db: Session, key: str, value: str) -> None:
    item = db.get(Setting, key)
    if item is None:
        db.add(Setting(key=key, value=value))
    else:
        item.value = value


def _month(value: str | None, contract: Contract) -> tuple[int, int]:
    try:
        tz = ZoneInfo(contract.timezone or "Europe/Madrid")
    except Exception:
        tz = ZoneInfo("Europe/Madrid")
    return periods.parse_month(value, tz)


async def _refresh_energy_readings(
    db: Session,
    contract: Contract,
    year: int,
    month: int,
) -> None:
    devices = list(
        db.scalars(select(Device).where(Device.enabled.is_(True)).order_by(Device.id)).all()
    )
    await energy_readings.refresh_readings(db, ha_client, contract, devices, year, month)


def _price_for(
    db: Session, contract: Contract, year: int, month: int
) -> tuple[TariffPrice | None, bool]:
    profile = profiles.get_profile(contract.tariff_profile_id)
    if profile.get("price_source") == "ree_pvpc":
        return prices.ensure_tariff_price(db, contract, year, month), False

    manual_price, manual_fallback = tariff.get_price_for_month(
        db, contract, year, month, source="manual"
    )
    # Un precio manual del mes exacto es una confirmación explícita del usuario
    # y debe prevalecer sobre el arrastre del mes anterior de Pepe.
    if manual_price is not None and not manual_fallback:
        return manual_price, False

    if str(profile.get("price_source", "")).startswith("pepe_api"):
        price, is_fallback = tariff.get_price_for_month(
            db, contract, year, month, source="pepe_api"
        )
        if price is not None:
            return price, is_fallback
    return manual_price, manual_fallback


def _estimate_rows(
    db: Session,
    contract: Contract,
    price: TariffPrice | None,
    year: int,
    month: int,
) -> tuple[
    list[tuple[Device, estimation.DeviceEstimate]],
    float,
    dict[str, float],
    dict | None,
    prices.PriceCurve,
]:
    factor = tariff.calibration_factor(db, contract)
    curve = (
        prices.build_month_curve(db, contract, price, year, month)
        if price is not None
        else prices.zero_month_curve(contract, year, month)
    )
    devices = list(
        db.scalars(select(Device).where(Device.enabled.is_(True)).order_by(Device.id)).all()
    )
    real_energy = energy_readings.readings_for_month(db, year, month)
    rows = []
    for device in devices:
        reading = real_energy.get(device.id)
        rows.append(
            (
                device,
                estimation.estimate_device_hourly(
                    device,
                    contract,
                    curve,
                    year,
                    month,
                    factor,
                    real_energy_kwh=reading.energy_kwh if reading is not None else None,
                    real_hourly=energy_readings.hourly_map(reading),
                ),
            )
        )
    by_period = {"P1": 0.0, "P2": 0.0, "P3": 0.0}
    energy_by_hour: dict[datetime, float] = {}
    for _device, est in rows:
        for p in periods.PERIOD_ORDER:
            by_period[p] += est.by_period.get(p, 0.0)
        for hour_dt, energy in est.hourly.items():
            energy_by_hour[hour_dt] = energy_by_hour.get(hour_dt, 0.0) + energy
    bill = None
    if price is not None:
        bill = tariff.bill_breakdown_hourly(
            contract,
            price,
            periods.month_days(year, month),
            energy_by_hour,
            curve,
        )
    return rows, factor, by_period, bill, curve


def _estimate_one(
    db: Session,
    contract: Contract,
    device: Device,
    year: int,
    month: int,
    real_energy_kwh: float | None = None,
    real_hourly: dict[datetime, float] | None = None,
) -> tuple[TariffPrice | None, prices.PriceCurve, estimation.DeviceEstimate, bool]:
    price, is_fallback = _price_for(db, contract, year, month)
    curve = (
        prices.build_month_curve(db, contract, price, year, month)
        if price is not None
        else prices.zero_month_curve(contract, year, month)
    )
    reading = (
        energy_readings.reading_for_device(db, device.id, year, month)
        if real_energy_kwh is None and device.id
        else None
    )
    if reading is not None:
        real_energy_kwh = reading.energy_kwh
        real_hourly = energy_readings.hourly_map(reading)
    est = estimation.estimate_device_hourly(
        device,
        contract,
        curve,
        year,
        month,
        tariff.calibration_factor(db, contract),
        real_energy_kwh=real_energy_kwh,
        real_hourly=real_hourly,
    )
    return price, curve, est, is_fallback


def _curve_cheap_windows(
    curve: prices.PriceCurve,
    tz: ZoneInfo,
    count: int = 4,
    duration_hours: int = 2,
) -> list[dict]:
    windows = prices.cheapest_windows(curve, duration_hours=duration_hours, count=count)
    now = datetime.now(tz)
    result = []
    for window in windows:
        start = datetime.fromisoformat(window["start"])
        end = datetime.fromisoformat(window["end"])
        if start.date() == now.date():
            prefix = "Hoy"
        elif start.date() == now.date() + timedelta(days=1):
            prefix = "Mañana"
        else:
            prefix = periods.WEEKDAYS_ES[start.weekday()].capitalize() + f" {start.day}"
        result.append(
            {
                **window,
                "label": f"{prefix}, {start.strftime('%H:%M')}–{end.strftime('%H:%M')}",
                "hours": window["hours"],
            }
        )
    return result


def _device_summary(
    device: Device,
    est: estimation.DeviceEstimate,
    price: TariffPrice | None,
    total_cost: float,
    total_energy: float,
) -> dict:
    share = (est.cost_eur / total_cost * 100.0) if total_cost > 0 else (
        (est.energy_kwh / total_energy * 100.0) if total_energy > 0 else 0.0
    )
    return {
        "id": device.id,
        "name": device.name,
        "category": device.category,
        "icon": device.icon or get_catalog_item(device.category).get("icon"),
        "area": device.area,
        "mode": device.mode,
        "power_active_w": device.power_active_w,
        "power_standby_w": device.power_standby_w,
        "duty_cycle_pct": device.duty_cycle_pct,
        "annual_kwh": device.annual_kwh,
        "hours_per_day": device.hours_per_day,
        "cycles_per_week": device.cycles_per_week,
        "minutes_per_cycle": device.minutes_per_cycle,
        "energy_per_cycle_kwh": device.energy_per_cycle_kwh,
        "always_plugged": device.always_plugged,
        "typical_windows": estimation.device_windows(device),
        "flexibility": device.flexibility,
        "entity_id": device.entity_id,
        "energy_entity_id": device.energy_entity_id,
        "energy_source": est.energy_source,
        "energy_resolution": est.energy_resolution,
        "enabled": device.enabled,
        "notes": device.notes,
        "is_demo": device.is_demo,
        "energy_kwh": est.energy_kwh,
        "active_kwh": est.active_kwh,
        "standby_kwh": est.standby_kwh,
        "cost": est.cost_eur,
        "min_cost": est.min_cost_eur,
        "max_cost": est.max_cost_eur,
        "share": share,
        "confidence": est.confidence,
        "by_period": est.by_period,
        "cost_by_period": est.cost_by_period,
        "periods": est.period_rows(price),
        "notes_estimate": est.notes,
    }


def _apply_payload(device: Device, payload: DeviceIn) -> None:
    item = get_catalog_item(payload.category)
    device.name = payload.name.strip()
    device.category = payload.category
    device.icon = payload.icon or item.get("icon")
    device.area = payload.area
    device.mode = payload.mode
    device.power_active_w = payload.power_active_w
    device.power_standby_w = payload.power_standby_w
    device.duty_cycle_pct = payload.duty_cycle_pct
    device.annual_kwh = payload.annual_kwh
    device.hours_per_day = payload.hours_per_day
    device.cycles_per_week = payload.cycles_per_week
    device.minutes_per_cycle = payload.minutes_per_cycle
    device.energy_per_cycle_kwh = payload.energy_per_cycle_kwh
    device.always_plugged = payload.always_plugged
    device.typical_windows_json = (
        json.dumps([window.model_dump() for window in payload.typical_windows], ensure_ascii=False)
        if payload.typical_windows
        else None
    )
    device.flexibility = payload.flexibility
    device.entity_id = payload.entity_id
    device.energy_entity_id = payload.energy_entity_id
    device.enabled = payload.enabled
    device.notes = payload.notes


def _device_from_payload(payload: DeviceIn) -> Device:
    device = Device(name=payload.name, category=payload.category, mode=payload.mode)
    _apply_payload(device, payload)
    device.id = 0
    device.is_demo = False
    return device


def _serialize_current_tariff(db: Session, contract: Contract, year: int, month: int) -> dict:
    price, is_fallback = _price_for(db, contract, year, month)
    days = periods.month_days(year, month)
    _rows, _factor, _by_period, bill, _curve = _estimate_rows(db, contract, price, year, month)
    fixed = bill
    calibration = tariff.get_latest_calibration(db, contract)
    return {
        "contract": ContractOut.model_validate(contract).model_dump(mode="json"),
        "profile": profiles.get_profile(contract.tariff_profile_id),
        "month": f"{year:04d}-{month:02d}",
        "month_label": periods.month_label_es(year, month),
        "days": days,
        "price": tariff.price_to_dict(price, year, month, is_fallback),
        "periods": tariff.period_price_list(price),
        "fixed": fixed,
        "price_mode": "hourly" if price and price.source == "ree_pvpc" else "period",
        "calibration_factor": tariff.calibration_factor(db, contract),
        "calibration": CalibrationOut.model_validate(calibration).model_dump(mode="json")
        if calibration
        else None,
    }


@router.get("/health")
def health() -> dict:
    return {"ok": True, "app": "EnergyHub", "version": APP_VERSION}


@router.get("/bootstrap")
async def bootstrap(db: Session = Depends(get_db)) -> dict:
    contract = tariff.get_active_contract(db)
    device_count = len(db.scalars(select(Device).where(Device.enabled.is_(True))).all())
    has_price = False
    if contract is not None:
        year, month = _month(None, contract)
        price, _fallback = _price_for(db, contract, year, month)
        has_price = price is not None
    status = await ha_client.get_status()
    return {
        "has_contract": contract is not None,
        "has_devices": device_count > 0,
        "has_price": has_price,
        "device_count": device_count,
        "demo_mode": _get_setting(db, "demo_mode", "0") == "1",
        "ha": status.__dict__,
        "app_version": APP_VERSION,
    }


@router.get("/catalog")
def catalog() -> dict:
    return {"items": CATALOG}


@router.get("/tariffs")
def tariffs() -> dict:
    return {
        "profiles": profiles.all_profiles(),
        "community_updated_at": "2026-11-16",
        "notes": (
            "Pepe y PVPC tienen precios automáticos. Los perfiles de mercado libre "
            "del catálogo comunitario son orientativos y requieren confirmar los precios."
        ),
    }


@router.get("/changelog")
async def changelog_endpoint() -> dict:
    result = await changelog.get_changelog()
    return result.as_dict()


@router.get("/contract")
def get_contract(db: Session = Depends(get_db)) -> dict:
    contract = tariff.get_active_contract(db)
    return {
        "contract": ContractOut.model_validate(contract).model_dump(mode="json") if contract else None
    }


@router.post("/contract")
def save_contract(payload: ContractIn, db: Session = Depends(get_db)) -> dict:
    contract = tariff.get_active_contract(db)
    data = payload.model_dump()
    if contract is None:
        contract = Contract(**data)
        db.add(contract)
    else:
        for key, value in data.items():
            setattr(contract, key, value)
        contract.is_active = True
    _set_setting(db, "setup_completed", "1")
    db.commit()
    db.refresh(contract)
    return {"contract": ContractOut.model_validate(contract).model_dump(mode="json")}


@router.get("/tariff/current")
async def current_tariff(
    month: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    db: Session = Depends(get_db),
) -> dict:
    contract = _contract_or_404(db)
    year, month_number = _month(month, contract)
    await _refresh_energy_readings(db, contract, year, month_number)
    return _serialize_current_tariff(db, contract, year, month_number)


@router.get("/tariff/calendar")
def tariff_calendar(
    days: int = Query(default=7, ge=1, le=31),
    db: Session = Depends(get_db),
) -> dict:
    contract = _contract_or_404(db)
    try:
        tz = ZoneInfo(contract.timezone or "Europe/Madrid")
    except Exception:
        tz = ZoneInfo("Europe/Madrid")
    now = datetime.now(tz)
    year, month_number = _month(None, contract)
    profile = profiles.get_profile(contract.tariff_profile_id)
    price, is_fallback = _price_for(db, contract, year, month_number)
    values = tariff.period_prices(price) if price is not None else {p: 0.0 for p in periods.PERIOD_ORDER}
    hourly_data = None
    if profile.get("price_source") == "ree_pvpc" and price is not None:
        start_hour = now.replace(minute=0, second=0, microsecond=0)
        curve = prices.build_range_curve(
            db, contract, price, start_hour, start_hour + timedelta(days=days)
        )
        chart_points = curve.points[:48]
        hourly_data = {
            "points": [point.as_dict() for point in chart_points],
            "missing_hours": sum(1 for point in chart_points if point.missing),
            "source": curve.source,
            "coverage": (
                sum(1 for point in chart_points if not point.missing) / len(chart_points)
                if chart_points
                else 0.0
            ),
        }
        cheap = _curve_cheap_windows(curve, tz, count=6, duration_hours=2)
    else:
        cheap = periods.next_cheap_windows(
            now,
            country=contract.country,
            region=contract.region,
            tz=tz,
            count=6,
        )
    result_days = []
    for offset in range(days):
        day = now.date() + timedelta(days=offset)
        windows = periods.day_windows(day, contract.country, contract.region)
        for window in windows:
            window["price"] = values.get(window["id"], 0.0)
        result_days.append(
            {
                "date": day.isoformat(),
                "weekday": periods.WEEKDAYS_ES[day.weekday()].capitalize(),
                "day": day.day,
                "month": periods.MONTHS_ES[day.month - 1],
                "is_holiday": periods.is_holiday(day, contract.country, contract.region),
                "is_today": day == now.date(),
                "windows": windows,
            }
        )
    return {
        "month": f"{year:04d}-{month_number:02d}",
        "price": tariff.price_to_dict(price, year, month_number, is_fallback),
        "profile": profile,
        "price_mode": "hourly" if profile.get("price_source") == "ree_pvpc" else "period",
        "periods": tariff.period_price_list(price),
        "days": result_days,
        "hourly": hourly_data,
        "cheap_windows": cheap,
    }


@router.get("/tariff/hourly")
def tariff_hourly(
    days: int = Query(default=2, ge=1, le=7),
    duration: int = Query(default=2, ge=1, le=8),
    db: Session = Depends(get_db),
) -> dict:
    contract = _contract_or_404(db)
    try:
        tz = ZoneInfo(contract.timezone or "Europe/Madrid")
    except Exception:
        tz = ZoneInfo("Europe/Madrid")
    now = datetime.now(tz).replace(minute=0, second=0, microsecond=0)
    year, month_number = _month(None, contract)
    price, is_fallback = _price_for(db, contract, year, month_number)
    profile = profiles.get_profile(contract.tariff_profile_id)
    if price is None:
        raise HTTPException(status_code=409, detail="No hay precios para calcular la curva horaria")
    curve = prices.build_range_curve(db, contract, price, now, now + timedelta(days=days))
    return {
        "profile": profile,
        "price_mode": "hourly" if profile.get("price_source") == "ree_pvpc" else "period",
        "price": tariff.price_to_dict(price, year, month_number, is_fallback),
        "curve": curve.as_dict(),
        "cheap_windows": _curve_cheap_windows(
            curve, tz, count=6, duration_hours=duration
        ),
    }


def _profile_contract(contract: Contract, profile_id: str) -> SimpleNamespace:
    defaults = profiles.profile_defaults(profile_id)
    return SimpleNamespace(
        power_p1_kw=contract.power_p1_kw,
        power_p2_kw=contract.power_p2_kw,
        tariff_profile_id=profile_id,
        has_pepephone_discount=bool(contract.has_pepephone_discount)
        and bool(defaults.get("supports_pepephone_discount")),
        bono_social_category=contract.bono_social_category,
        bono_social_energy_limit_kwh=contract.bono_social_energy_limit_kwh,
        service_fee_eur_month=defaults["service_fee_eur_month"],
        social_bond_eur_month=defaults["social_bond_eur_month"],
        meter_rent_eur_month=defaults["meter_rent_eur_month"],
        other_fees_eur_month=0.0,
        vat_rate=defaults["vat_rate"],
        electricity_tax_rate=defaults["electricity_tax_rate"],
        country=contract.country,
        region=contract.region,
        timezone=contract.timezone,
    )


@router.get("/comparator")
async def comparator(
    month: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    db: Session = Depends(get_db),
) -> dict:
    contract = _contract_or_404(db)
    year, month_number = _month(month, contract)
    await _refresh_energy_readings(db, contract, year, month_number)
    price, is_fallback = _price_for(db, contract, year, month_number)
    profile = profiles.get_profile(contract.tariff_profile_id)
    rows, _factor, _by_period, current_bill, current_curve = _estimate_rows(
        db, contract, price, year, month_number
    )
    if current_bill is None:
        raise HTTPException(status_code=409, detail="No hay precios actuales para comparar")
    energy_by_hour: dict[datetime, float] = {}
    for _device, est in rows:
        for hour_dt, energy in est.hourly.items():
            energy_by_hour[hour_dt] = energy_by_hour.get(hour_dt, 0.0) + energy
    days = periods.month_days(year, month_number)
    notes: list[str] = ["Misma potencia contratada y mismo consumo estimado para ambos escenarios."]
    pvpc_coverage = 1.0
    if profile.get("price_source") == "ree_pvpc":
        alternative_profile_id = "pepe_variable"
        alternative_price, _ = tariff.get_price_for_month(
            db, contract, year, month_number, source="pepe_api"
        )
        if alternative_price is None or alternative_price.source not in {"pepe_api", "manual"}:
            raise HTTPException(
                status_code=409,
                detail="No hay precios de Pepe guardados para comparar con PVPC",
            )
        alternative_contract = _profile_contract(contract, alternative_profile_id)
        alt_curve = prices.build_month_curve(
            db, alternative_contract, alternative_price, year, month_number
        )
        pvpc_available = current_curve.coverage > 0
        missing_hours = current_curve.missing_hours
        pvpc_coverage = current_curve.coverage
        if is_fallback:
            notes.append("El precio de Pepe es provisional.")
    else:
        alternative_profile_id = "pvpc_2td"
        alternative_contract = _profile_contract(contract, alternative_profile_id)
        first, last = periods.month_bounds(year, month_number)
        alternative_price = TariffPrice(
            contract_id=contract.id,
            valid_from=first,
            valid_to=last,
            month_label=periods.month_label_short(year, month_number),
            source="ree_pvpc",
            status="confirmed",
            p1_price=0.0,
            p2_price=0.0,
            p3_price=0.0,
            power_p1_price=float(profiles.get_profile(alternative_profile_id).get("power_p1_price") or 0.0),
            power_p2_price=float(profiles.get_profile(alternative_profile_id).get("power_p2_price") or 0.0),
            service_fee_eur_month=float(profiles.get_profile(alternative_profile_id).get("service_fee_eur_month") or 0.0),
            social_bond_eur_month=float(profiles.get_profile(alternative_profile_id).get("social_bond_eur_month") or 0.0),
            vat_rate=float(profiles.get_profile(alternative_profile_id).get("vat_rate") or 0.21),
            electricity_tax_rate=float(
                profiles.get_profile(alternative_profile_id).get("electricity_tax_rate") or 0.0511269632
            ),
        )
        try:
            alt_curve = prices.build_month_curve(
                db, alternative_contract, alternative_price, year, month_number
            )
        except pvpc.PvpcError as exc:
            raise HTTPException(
                status_code=502,
                detail=f"No se han podido cargar los precios PVPC: {exc}",
            ) from exc
        pvpc_available = alt_curve.coverage > 0
        missing_hours = alt_curve.missing_hours
        pvpc_coverage = alt_curve.coverage
        if is_fallback:
            notes.append("El precio de Pepe es provisional; la comparación puede variar.")
        if contract.bono_social_category != "none":
            notes.append("El bono social solo se aplica a PVPC; la alternativa PVPC lo incluye.")
    if missing_hours and pvpc_coverage < 0.95:
        notes.append(
            f"Faltan {missing_hours} horas de PVPC; se usa el precio medio disponible."
        )
    alternative_bill = tariff.bill_breakdown_hourly(
        alternative_contract,
        alternative_price,
        days,
        energy_by_hour,
        alt_curve,
    )
    current_total = current_bill["total"]
    alternative_total = alternative_bill["total"]
    return {
        "month": f"{year:04d}-{month_number:02d}",
        "current_total": current_total,
        "alternative_total": alternative_total,
        "savings_eur_month": current_total - alternative_total,
        "current_label": f"{profile.get('company', contract.provider)} · {profile.get('name', 'Tarifa actual')}",
        "alternative_label": (
            "PVPC 2.0TD" if alternative_profile_id == "pvpc_2td" else "Pepe Energy · Tarifa Variable"
        ),
        "current_energy_cost": current_bill["energy_cost"],
        "alternative_energy_cost": alternative_bill["energy_cost"],
        "pvpc_available": pvpc_available,
        "missing_hours": missing_hours,
        "pvpc_coverage": pvpc_coverage,
        "current_bono_social": current_bill.get("bono_social_discount", 0.0),
        "alternative_bono_social": alternative_bill.get("bono_social_discount", 0.0),
        "notes": notes,
    }


@router.get("/tariff/proposals")
def tariff_proposals(db: Session = Depends(get_db)) -> dict:
    contract = _contract_or_404(db)
    proposals = db.scalars(
        select(PriceProposal)
        .where(PriceProposal.contract_id == contract.id)
        .order_by(PriceProposal.fetched_at.desc(), PriceProposal.id.desc())
        .limit(20)
    ).all()
    return {
        "items": [
            PriceProposalOut.model_validate(proposal).model_dump(mode="json") for proposal in proposals
        ]
    }


@router.post("/tariff/pepe/fetch")
async def fetch_pepe(db: Session = Depends(get_db)) -> dict:
    contract = _contract_or_404(db)
    profile = profiles.get_profile(contract.tariff_profile_id)
    kind = "fixed" if profile.get("price_source") == "pepe_api_fixed" else "variable"
    try:
        offer = await pepe.fetch_pepe_last_month(kind=kind)
    except pepe.PepeFetchError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    proposal = db.scalars(
        select(PriceProposal).where(
            PriceProposal.contract_id == contract.id,
            PriceProposal.valid_from == offer.valid_from,
            PriceProposal.status == "pending",
        )
    ).first()
    if proposal is None:
        proposal = PriceProposal(contract_id=contract.id, valid_from=offer.valid_from)
        db.add(proposal)
    proposal.month_label = offer.month_label
    proposal.p1_price = offer.p1_price
    proposal.p2_price = offer.p2_price
    proposal.p3_price = offer.p3_price
    proposal.power_p1_price = offer.power_p1_price
    proposal.power_p2_price = offer.power_p2_price
    proposal.service_fee_eur_month = offer.service_fee_eur_month
    proposal.social_bond_eur_month = offer.social_bond_eur_month
    proposal.vat_rate = offer.vat_rate
    proposal.electricity_tax_rate = offer.electricity_tax_rate
    proposal.source = "pepe_api"
    proposal.status = "pending"
    proposal.raw_json = offer.raw_json
    proposal.fetched_at = offer.fetched_at
    proposal.error = None
    # Las propuestas de meses anteriores que sigan pendientes quedan superadas.
    db.execute(
        update(PriceProposal)
        .where(
            PriceProposal.contract_id == contract.id,
            PriceProposal.status == "pending",
            PriceProposal.valid_from != offer.valid_from,
        )
        .values(status="superseded")
    )
    db.commit()
    db.refresh(proposal)
    return {
        "proposal": PriceProposalOut.model_validate(proposal).model_dump(mode="json"),
        "message": "Precios detectados. Revísalos y confirma su aplicación.",
    }


@router.post("/tariff/pepe/confirm")
def confirm_pepe(payload: dict = Body(...), db: Session = Depends(get_db)) -> dict:
    contract = _contract_or_404(db)
    try:
        proposal_id = int(payload.get("proposal_id"))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="proposal_id no válido") from exc
    proposal = db.get(PriceProposal, proposal_id)
    if proposal is None or proposal.contract_id != contract.id:
        raise HTTPException(status_code=404, detail="Propuesta de precios no encontrada")
    price = tariff.upsert_price(
        db,
        contract,
        valid_from=proposal.valid_from,
        month_label=proposal.month_label,
        p1=proposal.p1_price,
        p2=proposal.p2_price,
        p3=proposal.p3_price,
        power_p1=proposal.power_p1_price,
        power_p2=proposal.power_p2_price,
        service_fee=proposal.service_fee_eur_month,
        social_bond=proposal.social_bond_eur_month,
        vat_rate=proposal.vat_rate,
        electricity_tax_rate=proposal.electricity_tax_rate,
        source=proposal.source,
        status="confirmed",
        raw_json=proposal.raw_json,
        notes="Confirmado desde la app.",
    )
    proposal.status = "applied"
    db.commit()
    year, month_number = _month(None, contract)
    current_price, fallback = _price_for(db, contract, year, month_number)
    return {
        "price": tariff.price_to_dict(price, proposal.valid_from.year, proposal.valid_from.month, False),
        "current": tariff.price_to_dict(current_price, year, month_number, fallback),
    }


@router.post("/tariff/prices")
def save_manual_price(payload: ManualPriceIn, db: Session = Depends(get_db)) -> dict:
    contract = _contract_or_404(db)
    year, month_number = periods.parse_month(payload.month)
    valid_from = date(year, month_number, 1)
    price = tariff.upsert_price(
        db,
        contract,
        valid_from=valid_from,
        month_label=periods.month_label_short(year, month_number),
        p1=payload.p1_price,
        p2=payload.p2_price,
        p3=payload.p3_price,
        power_p1=payload.power_p1_price,
        power_p2=payload.power_p2_price,
        service_fee=payload.service_fee_eur_month,
        social_bond=payload.social_bond_eur_month,
        vat_rate=payload.vat_rate,
        electricity_tax_rate=payload.electricity_tax_rate,
        source=payload.source,
        status="confirmed",
        notes=payload.notes,
    )
    return {"price": tariff.price_to_dict(price, year, month_number, False)}


@router.get("/devices")
async def list_devices(
    month: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    db: Session = Depends(get_db),
) -> dict:
    contract = tariff.get_active_contract(db)
    if contract is None:
        return {"items": [], "summary": {"energy_kwh": 0, "cost": 0, "count": 0}}
    year, month_number = _month(month, contract)
    await _refresh_energy_readings(db, contract, year, month_number)
    price, _fallback = _price_for(db, contract, year, month_number)
    rows, factor, _by_period, _bill, _curve = _estimate_rows(db, contract, price, year, month_number)
    total_cost = sum(est.cost_eur for _device, est in rows)
    total_energy = sum(est.energy_kwh for _device, est in rows)
    items = [
        _device_summary(device, est, price, total_cost, total_energy) for device, est in rows
    ]
    return {
        "items": items,
        "summary": {
            "energy_kwh": total_energy,
            "cost": total_cost,
            "count": len(items),
            "calibration_factor": factor,
            "price": tariff.price_to_dict(price, year, month_number, _fallback),
        },
    }


@router.post("/devices/preview")
async def preview_device(payload: DevicePreviewIn, db: Session = Depends(get_db)) -> dict:
    contract = _contract_or_404(db)
    year, month_number = _month(payload.month, contract)
    device = _device_from_payload(payload.device)
    real_energy = None
    real_hourly = None
    energy_error: str | None = None
    if device.mode == "entity" and device.energy_entity_id:
        if ha_client.configured:
            result = await energy_readings.cached_month_energy(
                ha_client,
                contract,
                str(device.energy_entity_id),
                year,
                month_number,
            )
            real_energy = result.energy_kwh
            real_hourly = result.hourly
            energy_error = result.error
        else:
            energy_error = "Home Assistant no está conectado; no se puede leer la entidad de energía."
    if device.id and real_energy is None:
        stored = energy_readings.reading_for_device(db, device.id, year, month_number)
        if stored is not None:
            real_energy = stored.energy_kwh
            real_hourly = energy_readings.hourly_map(stored)
    price, _curve, est, _fallback = _estimate_one(
        db,
        contract,
        device,
        year,
        month_number,
        real_energy_kwh=real_energy,
        real_hourly=real_hourly,
    )
    return {
        "energy_kwh": est.energy_kwh,
        "active_kwh": est.active_kwh,
        "standby_kwh": est.standby_kwh,
        "cost_eur": est.cost_eur,
        "min_cost_eur": est.min_cost_eur,
        "max_cost_eur": est.max_cost_eur,
        "confidence": est.confidence,
        "periods": est.period_rows(price),
        "typical_windows": estimation.device_windows(device),
        "notes": est.notes,
        "price_available": price is not None,
        "price_is_fallback": _fallback if price is not None else False,
        "price_month": f"{year:04d}-{month_number:02d}",
        "price_month_label": periods.month_label_es(year, month_number),
        "price_source": price.source if price is not None else None,
        "currency": contract.currency,
        "energy_source": est.energy_source,
        "energy_resolution": est.energy_resolution,
        "energy_entity_id": device.energy_entity_id,
        "energy_error": energy_error,
    }


@router.get("/devices/{device_id}/hourly")
async def device_hourly(
    device_id: int,
    month: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    db: Session = Depends(get_db),
) -> dict:
    """Return the hourly consumption profile of one device for a month."""
    contract = _contract_or_404(db)
    device = db.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado")
    year, month_number = _month(month, contract)
    real_energy = None
    real_hourly = None
    if device.mode == "entity" and device.energy_entity_id and ha_client.configured:
        result = await energy_readings.cached_month_energy(
            ha_client, contract, str(device.energy_entity_id), year, month_number
        )
        real_energy = result.energy_kwh
        real_hourly = result.hourly
    price, curve, est, is_fallback = _estimate_one(
        db,
        contract,
        device,
        year,
        month_number,
        real_energy_kwh=real_energy,
        real_hourly=real_hourly,
    )
    price_by_hour = {point.local_dt: point for point in curve.points}
    day_totals: dict[str, dict] = {}
    profile = [
        {"hour": hour, "energy_kwh": 0.0, "cost_eur": 0.0, "P1": 0.0, "P2": 0.0, "P3": 0.0}
        for hour in range(24)
    ]
    hours: list[dict] = []
    for moment, raw_energy in sorted(est.hourly.items()):
        try:
            energy = float(raw_energy or 0.0)
        except (TypeError, ValueError):
            continue
        if energy <= 0:
            continue
        point = price_by_hour.get(moment)
        if point is None:
            continue
        cost = energy * point.price
        hours.append(
            {
                "timestamp": moment.isoformat(),
                "date": moment.date().isoformat(),
                "hour": moment.hour,
                "energy_kwh": round(energy, 4),
                "price": point.price,
                "period": point.period,
                "cost_eur": round(cost, 4),
            }
        )
        row = profile[moment.hour]
        row["energy_kwh"] += energy
        row["cost_eur"] += cost
        row[point.period] += energy
        day = day_totals.setdefault(
            moment.date().isoformat(),
            {
                "date": moment.date().isoformat(),
                "energy_kwh": 0.0,
                "cost_eur": 0.0,
                "P1": 0.0,
                "P2": 0.0,
                "P3": 0.0,
            },
        )
        day["energy_kwh"] += energy
        day["cost_eur"] += cost
        day[point.period] += energy

    total_energy = sum(row["energy_kwh"] for row in profile)
    period_rows = est.period_rows(price)
    for row in period_rows:
        row["share"] = round((row["energy_kwh"] / total_energy * 100.0) if total_energy > 0 else 0.0, 2)
    top_period = max(period_rows, key=lambda row: row["energy_kwh"], default=None)
    top_hour = max(profile, key=lambda row: row["energy_kwh"], default=None)
    top_day = max(day_totals.values(), key=lambda row: row["energy_kwh"], default=None)
    return {
        "month": f"{year:04d}-{month_number:02d}",
        "month_label": periods.month_label_es(year, month_number),
        "energy_kwh": est.energy_kwh,
        "cost_eur": est.cost_eur,
        "energy_source": est.energy_source,
        "energy_resolution": est.energy_resolution,
        "confidence": est.confidence,
        "price_is_fallback": is_fallback if price is not None else False,
        "price_month_label": periods.month_label_es(year, month_number),
        "price_reference_month": (
            f"{price.valid_from.year:04d}-{price.valid_from.month:02d}" if price is not None else None
        ),
        "price_source": price.source if price is not None else None,
        "currency": contract.currency,
        "periods": period_rows,
        "profile": profile,
        "days": sorted(day_totals.values(), key=lambda row: row["date"]),
        "hours": hours,
        "top_period": top_period if top_period is not None and top_period["energy_kwh"] > 0 else None,
        "top_hour": (
            {
                "hour": top_hour["hour"],
                "label": f"{top_hour['hour']:02d}:00–{top_hour['hour'] + 1:02d}:00",
                "energy_kwh": round(top_hour["energy_kwh"], 4),
            }
            if top_hour is not None and top_hour["energy_kwh"] > 0
            else None
        ),
        "top_day": (
            {
                "date": top_day["date"],
                "energy_kwh": round(top_day["energy_kwh"], 4),
                "cost_eur": round(top_day["cost_eur"], 4),
            }
            if top_day is not None and top_day["energy_kwh"] > 0
            else None
        ),
        "notes": est.notes,
        "typical_windows": estimation.device_windows(device),
    }


@router.post("/devices")
def create_device(payload: DeviceIn, db: Session = Depends(get_db)) -> dict:
    contract = _contract_or_404(db)
    device = Device()
    _apply_payload(device, payload)
    db.add(device)
    db.commit()
    db.refresh(device)
    year, month_number = _month(None, contract)
    price, _curve, est, _fallback = _estimate_one(db, contract, device, year, month_number)
    return {"device": _device_summary(device, est, price, est.cost_eur, est.energy_kwh)}


@router.put("/devices/{device_id}")
def update_device(device_id: int, payload: DeviceIn, db: Session = Depends(get_db)) -> dict:
    contract = _contract_or_404(db)
    device = db.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado")
    _apply_payload(device, payload)
    db.commit()
    db.refresh(device)
    year, month_number = _month(None, contract)
    price, _curve, est, _fallback = _estimate_one(db, contract, device, year, month_number)
    return {"device": _device_summary(device, est, price, est.cost_eur, est.energy_kwh)}


@router.delete("/devices/{device_id}")
def delete_device(device_id: int, db: Session = Depends(get_db)) -> dict:
    device = db.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado")
    db.delete(device)
    db.commit()
    return {"ok": True}


@router.get("/dashboard")
async def dashboard(
    month: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    db: Session = Depends(get_db),
) -> dict:
    contract = _contract_or_404(db)
    year, month_number = _month(month, contract)
    await _refresh_energy_readings(db, contract, year, month_number)
    profile = profiles.get_profile(contract.tariff_profile_id)
    price, is_fallback = _price_for(db, contract, year, month_number)
    rows, factor, by_period, bill, curve = _estimate_rows(db, contract, price, year, month_number)
    total_cost = sum(est.cost_eur for _device, est in rows)
    total_energy = sum(est.energy_kwh for _device, est in rows)
    items = [
        _device_summary(device, est, price, total_cost, total_energy) for device, est in rows
    ]
    items.sort(key=lambda item: (item["cost"], item["energy_kwh"]), reverse=True)
    calibration = tariff.get_latest_calibration(db, contract)
    active_recs = recommendations.generate_recommendations(
        db,
        contract,
        price,
        is_fallback,
        year,
        month_number,
        rows,
        calibration,
        ha_configured=ha_client.configured,
    )
    try:
        tz = ZoneInfo(contract.timezone or "Europe/Madrid")
    except Exception:
        tz = ZoneInfo("Europe/Madrid")
    if profile.get("price_source") == "ree_pvpc" and price is not None:
        future_start = datetime.now(tz).replace(minute=0, second=0, microsecond=0)
        try:
            future_curve = prices.build_range_curve(
                db, contract, price, future_start, future_start + timedelta(days=7)
            )
            cheap = _curve_cheap_windows(future_curve, tz, count=4, duration_hours=2)
        except pvpc.PvpcError:
            cheap = _curve_cheap_windows(curve, tz, count=4, duration_hours=2)
    else:
        cheap = periods.next_cheap_windows(
            datetime.now(tz),
            country=contract.country,
            region=contract.region,
            tz=tz,
            count=4,
        )
    esios_entity = _get_setting(db, "esios_entity_id", "")
    esios = {
        "configured": bool(esios_entity),
        "entity_id": esios_entity or None,
        "connected": False,
        "price": None,
        "state": None,
        "unit": None,
    }
    if esios_entity and ha_client.configured:
        state = await ha_client.get_state(esios_entity)
        if state:
            attributes = state.get("attributes") or {}
            try:
                price_value = float(state.get("state"))
            except (TypeError, ValueError):
                price_value = None
            esios.update(
                {
                    "connected": True,
                    "price": price_value,
                    "state": state.get("state"),
                    "unit": attributes.get("unit_of_measurement"),
                }
            )
    confidence_values = {"alta": 100, "media": 60, "baja": 30}
    score = (
        sum(confidence_values.get(item["confidence"], 40) for item in items) / len(items)
        if items
        else 0
    )
    totals = {
        "energy_kwh": total_energy,
        "energy_cost": bill["energy_cost"] if bill else 0.0,
        "energy_cost_original": bill.get("energy_cost_original", 0.0) if bill else 0.0,
        "power_cost": bill["power_cost"] if bill else 0.0,
        "power_cost_original": bill.get("power_cost_original", 0.0) if bill else 0.0,
        "fees_total": bill["fees_total"] if bill else 0.0,
        "service_discount": bill.get("service_discount", 0.0) if bill else 0.0,
        "bono_social_discount": bill.get("bono_social_discount", 0.0) if bill else 0.0,
        "bono_social_percentage": bill.get("bono_social_percentage", 0.0) if bill else 0.0,
        "bono_social_applied": bill.get("bono_social_applied", False) if bill else False,
        "electricity_tax": bill["electricity_tax"] if bill else 0.0,
        "vat": bill["vat"] if bill else 0.0,
        "total": bill["total"] if bill else 0.0,
        "fixed_total": (bill["power_cost"] + bill["fees_total"] + bill["electricity_tax"] + bill["vat"])
        if bill
        else 0.0,
        "variable_cost": bill["energy_cost"] if bill else 0.0,
        "calibration_factor": factor,
        "confidence": "alta" if score >= 80 else "media" if score >= 55 else "baja",
        "confidence_score": round(score, 0),
        "missing_hours": curve.missing_hours if profile.get("price_source") == "ree_pvpc" else 0,
        "price_coverage": curve.coverage,
    }
    period_rows = []
    for p in periods.PERIOD_ORDER:
        price_value = getattr(price, f"p{periods.PERIOD_ORDER.index(p) + 1}_price", 0.0) if price else 0.0
        period_rows.append(
            {
                "id": p,
                "name": periods.PERIOD_NAMES[p],
                "energy_kwh": bill["by_period"].get(p, 0.0) if bill else by_period.get(p, 0.0),
                "cost": bill["cost_by_period"].get(p, 0.0) if bill else 0.0,
                "price": price_value,
            }
        )
    return {
        "month": f"{year:04d}-{month_number:02d}",
        "month_label": periods.month_label_es(year, month_number),
        "contract": ContractOut.model_validate(contract).model_dump(mode="json"),
        "profile": profile,
        "price": tariff.price_to_dict(price, year, month_number, is_fallback),
        "price_mode": "hourly" if profile.get("price_source") == "ree_pvpc" else "period",
        "totals": totals,
        "by_period": period_rows,
        "devices": items,
        "top_devices": items[:5],
        "next_cheap_windows": cheap,
        "recommendations_count": len(active_recs),
        "esios": esios,
        "data_quality": {
            "score": round(score, 0),
            "label": totals["confidence"],
            "calibrated": calibration is not None,
            "devices": len(items),
            "calibration_factor": factor,
        },
        "setup": {
            "needs_price": price is None
            or (profile.get("price_source") == "ree_pvpc" and curve.coverage <= 0),
            "needs_devices": len(items) == 0,
            "needs_calibration": calibration is None,
        },
    }


@router.get("/recommendations")
async def list_recommendations(db: Session = Depends(get_db)) -> dict:
    contract = _contract_or_404(db)
    year, month_number = _month(None, contract)
    await _refresh_energy_readings(db, contract, year, month_number)
    price, is_fallback = _price_for(db, contract, year, month_number)
    rows, _factor, _by_period, _bill, _curve = _estimate_rows(db, contract, price, year, month_number)
    calibration = tariff.get_latest_calibration(db, contract)
    recs = recommendations.generate_recommendations(
        db,
        contract,
        price,
        is_fallback,
        year,
        month_number,
        rows,
        calibration,
        ha_configured=ha_client.configured,
    )
    devices = {device.id: device for device, _est in rows}
    return {
        "items": [
            recommendations.recommendation_payload(rec, devices.get(rec.device_id), ha_client.configured)
            for rec in recs
        ]
    }


@router.post("/recommendations/{rec_id}/dismiss")
def dismiss_recommendation(rec_id: str, db: Session = Depends(get_db)) -> dict:
    rec = db.get(Recommendation, rec_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Recomendación no encontrada")
    recommendations.mark_dismissed(db, rec)
    return {"ok": True}


def _automation_payload(kind: str, device: Device, rec: Recommendation) -> dict:
    if kind == "reminder":
        return {
            "alias": f"EnergyHub · {rec.title}",
            "description": "Creado por EnergyHub. Te avisa cuando empieza el tramo valle. Revisa el horario antes de usarlo.",
            "mode": "single",
            "trigger": [{"platform": "time", "at": "00:05:00"}],
            "condition": [],
            "action": [
                {
                    "service": "persistent_notification.create",
                    "data": {
                        "title": "EnergyHub · Hora valle",
                        "message": f"Es un buen momento para usar {device.name}. Estás en tramo valle.",
                    },
                }
            ],
        }
    return {
        "alias": f"EnergyHub · Apagar {device.name}",
        "description": "Creado por EnergyHub. Apaga el dispositivo al empezar el tramo valle. Revisa que sea seguro.",
        "mode": "single",
        "trigger": [{"platform": "time", "at": "00:00:00"}],
        "condition": [],
        "action": [
            {
                "service": "homeassistant.turn_off",
                "target": {"entity_id": device.entity_id},
            }
        ],
    }


@router.post("/recommendations/{rec_id}/create-automation")
async def create_recommendation_automation(rec_id: str, db: Session = Depends(get_db)) -> dict:
    rec = db.get(Recommendation, rec_id)
    if rec is None or not rec.automation_kind:
        raise HTTPException(status_code=404, detail="Automatización no disponible")
    device = db.get(Device, rec.device_id) if rec.device_id else None
    if device is None:
        raise HTTPException(status_code=400, detail="La recomendación no tiene un dispositivo asociado")
    if not ha_client.configured:
        raise HTTPException(
            status_code=400,
            detail="Home Assistant no está configurado. Copia el YAML y pégalo manualmente.",
        )
    if rec.automation_kind == "turn_off" and not ha.is_controllable(device.entity_id):
        raise HTTPException(status_code=400, detail="El dispositivo no tiene una entidad de control")
    payload = _automation_payload(rec.automation_kind, device, rec)
    alias = payload["alias"]
    slug = re.sub(r"[^a-z0-9]+", "_", rec.title.lower()).strip("_")[:48]
    automation_id = f"energyhub_{slug}_{uuid.uuid4().hex[:6]}"
    try:
        await ha_client.create_automation(automation_id, payload)
    except ha.HaNotConfigured as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ha.HaError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    log = AutomationLog(
        recommendation_id=rec.id,
        ha_automation_id=automation_id,
        alias=alias,
        payload_json=json.dumps(payload, ensure_ascii=False),
        status="created",
    )
    db.add(log)
    db.commit()
    return {"ok": True, "automation_id": automation_id, "alias": alias}


@router.get("/automations")
def list_automations(db: Session = Depends(get_db)) -> dict:
    logs = db.scalars(
        select(AutomationLog).where(AutomationLog.status == "created").order_by(AutomationLog.id.desc())
    ).all()
    return {
        "items": [
            {
                "id": log.id,
                "automation_id": log.ha_automation_id,
                "alias": log.alias,
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ]
    }


@router.delete("/automations/{automation_id}")
async def delete_automation(automation_id: str, db: Session = Depends(get_db)) -> dict:
    log = db.scalars(
        select(AutomationLog).where(AutomationLog.ha_automation_id == automation_id)
    ).first()
    if log is None:
        raise HTTPException(status_code=404, detail="Automatización no encontrada")
    try:
        await ha_client.delete_automation(automation_id)
    except ha.HaError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    log.status = "deleted"
    db.commit()
    return {"ok": True}


@router.post("/calibrations")
def create_calibration(payload: CalibrationIn, db: Session = Depends(get_db)) -> dict:
    contract = _contract_or_404(db)
    year, month_number = periods.parse_month(payload.month)
    price, _is_fallback = _price_for(db, contract, year, month_number)
    rows, _factor, by_period, bill, _curve = _estimate_rows(db, contract, price, year, month_number)
    estimated_kwh = sum(est.energy_kwh for _device, est in rows)
    if estimated_kwh <= 0:
        raise HTTPException(
            status_code=400,
            detail="No hay consumo estimado para ese mes. Añade dispositivos antes de calibrar.",
        )
    actual = float(payload.actual_kwh)
    factor = max(0.25, min(4.0, actual / estimated_kwh))
    start, end = periods.month_bounds(year, month_number)
    calibration = Calibration(
        contract_id=contract.id,
        period_start=start,
        period_end=end,
        actual_kwh=actual,
        actual_cost_eur=payload.actual_cost_eur,
        estimated_kwh=estimated_kwh,
        estimated_cost_eur=bill["total"] if bill else 0.0,
        factor=factor,
        notes=payload.notes,
    )
    db.add(calibration)
    db.commit()
    db.refresh(calibration)
    return {
        "calibration": CalibrationOut.model_validate(calibration).model_dump(mode="json"),
        "factor": factor,
        "estimated_kwh": estimated_kwh,
        "estimated_cost": bill["total"] if bill else 0.0,
    }


@router.get("/calibrations")
def list_calibrations(db: Session = Depends(get_db)) -> dict:
    contract = _contract_or_404(db)
    items = db.scalars(
        select(Calibration)
        .where(Calibration.contract_id == contract.id)
        .order_by(Calibration.created_at.desc())
    ).all()
    return {
        "items": [CalibrationOut.model_validate(item).model_dump(mode="json") for item in items],
        "factor": tariff.calibration_factor(db, contract),
    }


@router.get("/ha/status")
async def ha_status(refresh: bool = Query(default=False)) -> dict:
    status = await ha_client.get_status()
    return status.__dict__


@router.get("/ha/entities")
async def ha_entities(kind: str = Query(default="all")) -> dict:
    if not ha_client.configured:
        return {"configured": False, "items": []}
    try:
        items = await ha_client.list_entities(None if kind == "all" else kind)
    except ha.HaError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"configured": True, "items": items}


@router.get("/ha/areas")
async def ha_areas() -> dict:
    if not ha_client.configured:
        return {"configured": False, "items": []}
    try:
        items = await ha_client.get_areas()
    except ha.HaError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"configured": True, "items": items}


@router.get("/settings")
def get_settings(db: Session = Depends(get_db)) -> dict:
    return {
        "esios_entity_id": _get_setting(db, "esios_entity_id", ""),
        "language": _get_setting(db, "language", "es"),
        "theme": _get_setting(db, "theme", "system"),
        "demo_mode": _get_setting(db, "demo_mode", "0") == "1",
    }


@router.put("/settings")
def update_settings(payload: SettingsUpdate, db: Session = Depends(get_db)) -> dict:
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        if key == "esios_entity_id":
            _set_setting(db, key, value or "")
        elif key in {"language", "theme"} and value:
            _set_setting(db, key, value)
    db.commit()
    return get_settings(db)


@router.post("/demo/seed")
def seed_demo(db: Session = Depends(get_db)) -> dict:
    contract = demo.seed_demo(db)
    return {"ok": True, "contract": ContractOut.model_validate(contract).model_dump(mode="json")}


@router.post("/demo/reset")
def reset_demo(db: Session = Depends(get_db)) -> dict:
    demo.reset_all(db)
    return {"ok": True}


@router.get("/export")
def export_data(db: Session = Depends(get_db)) -> Response:
    contract = tariff.get_active_contract(db)
    payload: dict = {"app": "EnergyHub", "version": APP_VERSION, "exported_at": datetime.now(timezone.utc).isoformat()}
    if contract:
        prices = db.scalars(
            select(TariffPrice).where(TariffPrice.contract_id == contract.id).order_by(TariffPrice.valid_from)
        ).all()
        devices = db.scalars(select(Device).order_by(Device.id)).all()
        calibrations = db.scalars(
            select(Calibration).where(Calibration.contract_id == contract.id).order_by(Calibration.id)
        ).all()
        settings = db.scalars(select(Setting)).all()
        payload.update(
            {
                "contract": ContractOut.model_validate(contract).model_dump(mode="json"),
                "prices": [
                    {
                        "valid_from": price.valid_from.isoformat(),
                        "valid_to": price.valid_to.isoformat() if price.valid_to else None,
                        "month_label": price.month_label,
                        "source": price.source,
                        "status": price.status,
                        "p1_price": price.p1_price,
                        "p2_price": price.p2_price,
                        "p3_price": price.p3_price,
                        "power_p1_price": price.power_p1_price,
                        "power_p2_price": price.power_p2_price,
                        "service_fee_eur_month": price.service_fee_eur_month,
                        "social_bond_eur_month": price.social_bond_eur_month,
                        "vat_rate": price.vat_rate,
                        "electricity_tax_rate": price.electricity_tax_rate,
                    }
                    for price in prices
                ],
                "devices": [DeviceOut.model_validate(device).model_dump(mode="json") for device in devices],
                "calibrations": [
                    CalibrationOut.model_validate(calibration).model_dump(mode="json")
                    for calibration in calibrations
                ],
                "settings": {item.key: item.value for item in settings if item.key != "demo_mode"},
            }
        )
    return Response(
        content=json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="energyhub-export.json"'},
    )
