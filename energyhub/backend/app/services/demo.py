from __future__ import annotations

from datetime import date

from sqlalchemy import delete
from sqlalchemy.orm import Session

from ..catalog import get_catalog_item
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
from .tariff import upsert_price


def reset_all(db: Session) -> None:
    db.execute(delete(AutomationLog))
    db.execute(delete(Recommendation))
    db.execute(delete(Calibration))
    db.execute(delete(Device))
    db.execute(delete(PriceProposal))
    db.execute(delete(TariffPrice))
    db.execute(delete(Contract))
    db.execute(delete(Setting))
    db.commit()


def set_setting(db: Session, key: str, value: str) -> None:
    item = db.get(Setting, key)
    if item is None:
        item = Setting(key=key, value=value)
        db.add(item)
    else:
        item.value = value


def seed_demo(db: Session) -> Contract:
    reset_all(db)
    contract = Contract(
        name="Casa de ejemplo",
        provider="Pepe Energy",
        country="ES",
        region=None,
        timezone="Europe/Madrid",
        tariff_type="pepe_variable",
        access_toll="2.0TD",
        segment="1",
        power_p1_kw=4.6,
        power_p2_kw=4.6,
        service_fee_eur_month=3.996196,
        social_bond_eur_month=0.908639,
        meter_rent_eur_month=0.81,
        other_fees_eur_month=0.0,
        vat_rate=0.21,
        electricity_tax_rate=0.0511269632,
        currency="EUR",
        billing_day=1,
        is_active=True,
        notes="Datos de ejemplo de EnergyHub.",
    )
    db.add(contract)
    db.commit()
    db.refresh(contract)

    # Precio publicado por Pepe para octubre de 2026 (API pública usada por su web).
    upsert_price(
        db,
        contract,
        valid_from=date(2026, 10, 1),
        month_label="Octubre 2026",
        p1=0.404644,
        p2=0.318715,
        p3=0.283266,
        power_p1=0.075903,
        power_p2=0.001987,
        service_fee=3.996196,
        social_bond=0.908639,
        vat_rate=0.21,
        electricity_tax_rate=0.0511269632,
        source="pepe_api",
        notes="Precio de referencia de la API pública de Pepe. No es una tarifa contratada.",
    )

    samples = [
        ("Nevera", "fridge", "Cocina", {"power_active_w": 150, "duty_cycle_pct": 35, "annual_kwh": None}),
        ("Vitrocerámica", "vitro", "Cocina", {"hours_per_day": 1.0, "power_active_w": 2000}),
        ("Lavadora", "washing_machine", "Lavadero", {"cycles_per_week": 4, "minutes_per_cycle": 90, "energy_per_cycle_kwh": 0.9}),
        ("Lavavajillas", "dishwasher", "Cocina", {"cycles_per_week": 5, "minutes_per_cycle": 120, "energy_per_cycle_kwh": 0.8}),
        ("Televisión", "tv", "Salón", {"hours_per_day": 4, "power_active_w": 100, "power_standby_w": 0.5}),
        ("Router", "router", "Salón", {"power_active_w": 10, "duty_cycle_pct": 100, "annual_kwh": 87.6}),
        ("Horno", "oven", "Cocina", {"hours_per_day": 0.75, "power_active_w": 2500}),
        ("Termo eléctrico", "water_heater", "Baño", {"hours_per_day": 2, "power_active_w": 1500}),
        ("Luces", "lighting", "Salón", {"hours_per_day": 4, "power_active_w": 60}),
        ("Ordenador", "computer", "Despacho", {"hours_per_day": 5, "power_active_w": 150, "power_standby_w": 1.5}),
    ]

    for name, category, area, extra in samples:
        item = get_catalog_item(category)
        device = Device(
            name=name,
            category=category,
            icon=item["icon"],
            area=area,
            mode=extra.get("mode", item["mode"]),
            power_active_w=extra.get("power_active_w", item["power_active_w"]),
            power_standby_w=extra.get("power_standby_w", item["power_standby_w"]),
            duty_cycle_pct=extra.get("duty_cycle_pct", item["duty_cycle_pct"]),
            annual_kwh=extra.get("annual_kwh", item["annual_kwh"]),
            hours_per_day=extra.get("hours_per_day", item.get("hours_per_day", item["hours_per_day"])),
            cycles_per_week=extra.get("cycles_per_week", item["cycles_per_week"]),
            minutes_per_cycle=extra.get("minutes_per_cycle", item["minutes_per_cycle"]),
            energy_per_cycle_kwh=extra.get("energy_per_cycle_kwh", item["energy_per_cycle_kwh"]),
            always_plugged=item["always_plugged"],
            flexibility=item["flexibility"],
            enabled=True,
            is_demo=True,
        )
        db.add(device)

    set_setting(db, "demo_mode", "1")
    set_setting(db, "setup_completed", "1")
    set_setting(db, "language", "es")
    db.commit()
    return contract


def has_data(db: Session) -> bool:
    return db.query(Contract).count() > 0
