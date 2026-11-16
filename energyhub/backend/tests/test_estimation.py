from __future__ import annotations

from datetime import date

from app.models import Contract, Device, TariffPrice
from app.services.estimation import estimate_device


def make_contract() -> Contract:
    return Contract(
        id=1,
        name="Test",
        provider="Pepe Energy",
        country="ES",
        timezone="Europe/Madrid",
        power_p1_kw=4.6,
        power_p2_kw=4.6,
        service_fee_eur_month=3.996196,
        social_bond_eur_month=0.908639,
        meter_rent_eur_month=0.81,
        vat_rate=0.21,
        electricity_tax_rate=0.0511269632,
    )


def make_price() -> TariffPrice:
    return TariffPrice(
        id=1,
        contract_id=1,
        valid_from=date(2026, 10, 1),
        month_label="Octubre 2026",
        p1_price=0.404644,
        p2_price=0.318715,
        p3_price=0.283266,
        power_p1_price=0.075903,
        power_p2_price=0.001987,
        service_fee_eur_month=3.996196,
        social_bond_eur_month=0.908639,
        vat_rate=0.21,
        electricity_tax_rate=0.0511269632,
    )


def make_device(**overrides) -> Device:
    data = {
        "id": 1,
        "name": "Aparato",
        "category": "other",
        "mode": "always_on",
        "power_active_w": 100,
        "power_standby_w": 0,
        "duty_cycle_pct": 100,
        "always_plugged": True,
        "flexibility": "none",
        "enabled": True,
    }
    data.update(overrides)
    return Device(**data)


def test_always_on_with_annual_kwh() -> None:
    device = make_device(category="fridge", annual_kwh=200, power_active_w=150, duty_cycle_pct=35)
    est = estimate_device(device, make_contract(), make_price(), 2026, 11)
    assert abs(est.energy_kwh - (200 / 365 * 30)) < 0.01
    assert est.confidence == "alta"
    assert est.cost_eur > 0
    assert abs(est.min_cost_eur - est.cost_eur) < 0.001
    assert abs(est.max_cost_eur - est.cost_eur) < 0.001


def test_hours_per_day_and_period_breakdown() -> None:
    device = make_device(
        category="vitro",
        mode="hours_per_day",
        power_active_w=2000,
        hours_per_day=1,
        flexibility="none",
    )
    est = estimate_device(device, make_contract(), make_price(), 2026, 11)
    assert abs(est.energy_kwh - 60) < 0.01
    assert sum(est.by_period.values()) == 60
    assert est.by_period["P1"] > 0
    assert est.by_period["P3"] > 0
    assert est.min_cost_eur < est.cost_eur < est.max_cost_eur


def test_cycles_and_standby() -> None:
    device = make_device(
        category="washing_machine",
        mode="cycles",
        power_active_w=600,
        cycles_per_week=4,
        minutes_per_cycle=90,
        energy_per_cycle_kwh=0.9,
        power_standby_w=0.5,
        always_plugged=True,
        flexibility="flexible",
    )
    est = estimate_device(device, make_contract(), make_price(), 2026, 11)
    expected_active = 0.9 * 4 * 30 / 7
    assert abs(est.active_kwh - expected_active) < 0.01
    assert est.standby_kwh > 0
    assert est.energy_kwh > est.active_kwh


def test_calibration_factor_scales_energy() -> None:
    device = make_device(category="vitro", mode="hours_per_day", power_active_w=2000, hours_per_day=1)
    base = estimate_device(device, make_contract(), make_price(), 2026, 11)
    calibrated = estimate_device(device, make_contract(), make_price(), 2026, 11, calibration=2.0)
    assert abs(calibrated.energy_kwh - base.energy_kwh * 2) < 0.01
    assert abs(calibrated.cost_eur - base.cost_eur * 2) < 0.01


def test_without_price_costs_are_zero() -> None:
    device = make_device(category="vitro", mode="hours_per_day", power_active_w=2000, hours_per_day=1)
    est = estimate_device(device, make_contract(), None, 2026, 11)
    assert est.energy_kwh > 0
    assert est.cost_eur == 0
    assert any("Sin precios" in note for note in est.notes)
