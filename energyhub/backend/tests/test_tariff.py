from __future__ import annotations

from datetime import date

from app.models import Contract, TariffPrice
from app.services.tariff import bill_breakdown, fixed_breakdown


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
        other_fees_eur_month=0.0,
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


def test_fixed_breakdown_matches_pepe_terms() -> None:
    result = fixed_breakdown(make_contract(), make_price(), 30)
    expected_power = (4.6 * 0.075903 + 4.6 * 0.001987) * 30
    assert abs(result["power_cost"] - expected_power) < 0.001
    assert abs(result["fees_total"] - (3.996196 + 0.908639 + 0.81)) < 0.001
    assert result["total"] > result["power_cost"]


def test_bill_breakdown_energy_and_taxes() -> None:
    result = bill_breakdown(
        make_contract(),
        make_price(),
        30,
        {"P1": 100.0, "P2": 50.0, "P3": 50.0},
    )
    expected_energy = 100 * 0.404644 + 50 * 0.318715 + 50 * 0.283266
    assert abs(result["energy_cost"] - expected_energy) < 0.001
    assert result["electricity_tax"] > 0
    assert result["vat"] > 0
    assert result["total"] == (
        result["energy_cost"]
        + result["power_cost"]
        + result["fees_total"]
        + result["electricity_tax"]
        + result["vat"]
    )
