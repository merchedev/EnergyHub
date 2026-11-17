from __future__ import annotations

from datetime import date

import pytest

from app.models import Contract, Device, TariffPrice
from app.services import comparison, estimation


def make_contract() -> Contract:
    return Contract(
        id=1,
        name="Casa test",
        provider="Pepe Energy",
        country="ES",
        timezone="Europe/Madrid",
        tariff_profile_id="pepe_variable",
        vat_rate=0.21,
        electricity_tax_rate=0.0511269632,
    )


def make_price(
    p1: float = 0.404644,
    p2: float = 0.318715,
    p3: float = 0.283266,
    source: str = "manual",
) -> TariffPrice:
    return TariffPrice(
        contract_id=1,
        valid_from=date(2026, 11, 1),
        source=source,
        p1_price=p1,
        p2_price=p2,
        p3_price=p3,
        vat_rate=0.21,
        electricity_tax_rate=0.0511269632,
    )


def make_device(
    mode: str = "entity",
    flexibility: str = "flexible",
) -> Device:
    return Device(
        id=1,
        name="Lavadora",
        category="washing_machine",
        mode=mode,
        flexibility=flexibility,
        enabled=True,
    )


def make_estimate(
    p1: float = 0.0,
    p2: float = 0.0,
    p3: float = 9.9,
    price: TariffPrice | None = None,
) -> estimation.DeviceEstimate:
    price = price or make_price()
    cost = p1 * price.p1_price + p2 * price.p2_price + p3 * price.p3_price
    return estimation.DeviceEstimate(
        energy_kwh=p1 + p2 + p3,
        active_kwh=p1 + p2 + p3,
        standby_kwh=0.0,
        cost_eur=cost,
        by_period={"P1": p1, "P2": p2, "P3": p3},
        cost_by_period={
            "P1": p1 * price.p1_price,
            "P2": p2 * price.p2_price,
            "P3": p3 * price.p3_price,
        },
        confidence="alta",
    )


def test_all_valle_reports_savings_and_no_potential() -> None:
    contract = make_contract()
    price = make_price()
    device = make_device()
    est = make_estimate(p3=9.9)

    comp = comparison.device_comparison(device, est, price, contract)
    assert comp is not None
    assert comp.energy_kwh == pytest.approx(9.9)
    assert comp.actual_cost_eur == pytest.approx(9.9 * price.p3_price, abs=1e-3)
    assert comp.all_p1_cost_eur == pytest.approx(9.9 * price.p1_price, abs=1e-3)
    assert comp.all_p2_cost_eur == pytest.approx(9.9 * price.p2_price, abs=1e-3)
    assert comp.all_p3_cost_eur == pytest.approx(9.9 * price.p3_price, abs=1e-3)
    assert comp.savings_vs_p1_eur == pytest.approx(9.9 * (price.p1_price - price.p3_price), abs=1e-3)
    assert comp.valle_share == 100.0
    assert comp.savings_captured_pct == 100.0
    assert comp.shiftable_energy_kwh == 0.0
    assert comp.shiftable_saving_eur == 0.0
    assert comp.is_flexible is True
    assert comp.note and "Todo el consumo está en valle" in comp.note
    gross = (1 + contract.electricity_tax_rate) * (1 + contract.vat_rate)
    assert comp.savings_vs_p1_with_taxes_eur == pytest.approx(
        9.9 * (price.p1_price - price.p3_price) * gross,
        abs=1e-3,
    )


def test_flexible_device_has_configured_potential() -> None:
    contract = make_contract()
    price = make_price()
    device = make_device(mode="cycles", flexibility="flexible")
    est = make_estimate(p1=10.0, p2=5.0, p3=5.0)

    comp = comparison.device_comparison(
        device,
        est,
        price,
        contract,
        shift_flexible_pct=80,
    )
    assert comp is not None
    assert comp.shift_factor == pytest.approx(0.8)
    expected = 0.8 * (
        10.0 * (price.p1_price - price.p3_price) + 5.0 * (price.p2_price - price.p3_price)
    )
    assert comp.shiftable_energy_kwh == pytest.approx(15.0)
    assert comp.shiftable_saving_eur == pytest.approx(expected, abs=1e-3)


def test_semi_flexible_and_always_on() -> None:
    contract = make_contract()
    price = make_price()
    est = make_estimate(p1=10.0, p2=5.0, p3=5.0)

    semi = comparison.device_comparison(
        make_device(mode="hours_per_day", flexibility="semi"),
        est,
        price,
        contract,
        shift_semi_pct=20,
    )
    assert semi is not None
    assert semi.shift_factor == pytest.approx(0.2)
    assert semi.is_flexible is True

    always_on = comparison.device_comparison(
        make_device(mode="always_on", flexibility="flexible"),
        est,
        price,
        contract,
    )
    assert always_on is not None
    assert always_on.is_flexible is False
    assert always_on.shiftable_saving_eur == 0.0
    assert always_on.note and "Consumo continuo" in always_on.note


def test_fixed_tariff_has_no_period_difference() -> None:
    contract = make_contract()
    price = make_price(p1=0.2, p2=0.2, p3=0.2, source="pepe_api")
    comp = comparison.device_comparison(
        make_device(),
        make_estimate(price=price),
        price,
        contract,
    )
    assert comp is not None
    assert comp.has_period_difference is False
    assert comp.savings_vs_p1_eur == pytest.approx(0.0, abs=1e-3)
    assert comp.note and "mismo precio" in comp.note


def test_no_price_returns_none() -> None:
    comp = comparison.device_comparison(make_device(), make_estimate(), None, make_contract())
    assert comp is None


def test_aggregate_comparisons_sums_devices() -> None:
    contract = make_contract()
    price = make_price()
    first = comparison.device_comparison(
        make_device(), make_estimate(p3=10.0), price, contract
    )
    second = comparison.device_comparison(
        make_device(mode="hours_per_day", flexibility="semi"),
        make_estimate(p1=5.0, p3=5.0),
        price,
        contract,
    )
    assert first is not None
    assert second is not None
    total = comparison.aggregate_comparisons([first, second])
    assert total is not None
    assert total.energy_kwh == pytest.approx(20.0)
    assert total.actual_cost_eur == pytest.approx(
        first.actual_cost_eur + second.actual_cost_eur
    )
    assert total.all_p1_cost_eur == pytest.approx(first.all_p1_cost_eur + second.all_p1_cost_eur, abs=1e-3)
    assert total.shiftable_saving_eur == pytest.approx(first.shiftable_saving_eur + second.shiftable_saving_eur, abs=1e-3)
    assert total.by_period["P1"] == pytest.approx(5.0)
    assert total.by_period["P3"] == pytest.approx(15.0)
