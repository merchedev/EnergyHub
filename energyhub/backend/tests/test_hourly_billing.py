from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import Contract, Device, TariffPrice
from app.services import estimation, prices, pvpc, tariff
from app.services.pvpc import parse_ree_payload


def make_contract(profile_id: str = "pepe_variable", **overrides) -> Contract:
    data = {
        "id": 1,
        "provider": "Pepe Energy",
        "country": "ES",
        "timezone": "Europe/Madrid",
        "tariff_profile_id": profile_id,
        "power_p1_kw": 4.6,
        "power_p2_kw": 4.6,
        "service_fee_eur_month": 3.996196,
        "social_bond_eur_month": 0.908639,
        "meter_rent_eur_month": 0.81,
        "vat_rate": 0.21,
        "electricity_tax_rate": 0.0511269632,
        "has_pepephone_discount": False,
        "bono_social_category": "none",
        "bono_social_energy_limit_kwh": 1587,
    }
    data.update(overrides)
    return Contract(**data)


def make_price(profile_id: str = "pepe_variable") -> TariffPrice:
    return TariffPrice(
        contract_id=1,
        valid_from=date(2026, 11, 1),
        month_label="Noviembre 2026",
        source="ree_pvpc" if profile_id == "pvpc_2td" else "manual",
        status="confirmed",
        p1_price=0.2,
        p2_price=0.2,
        p3_price=0.2,
        power_p1_price=0.075903,
        power_p2_price=0.001987,
        service_fee_eur_month=0.0 if profile_id == "pvpc_2td" else 3.996196,
        social_bond_eur_month=0.908639,
        vat_rate=0.21,
        electricity_tax_rate=0.0511269632,
    )


def test_parse_ree_pvpc_payload() -> None:
    payload = {
        "included": [
            {
                "type": "PVPC",
                "id": "1001",
                "attributes": {
                    "values": [
                        {"value": 200.0, "datetime": "2026-11-15T00:00:00+01:00"},
                        {"value": 150.0, "datetime": "2026-11-15T01:00:00+01:00"},
                    ]
                },
            }
        ]
    }
    prices_map = parse_ree_payload(payload)
    assert len(prices_map) == 2
    timestamps = sorted(prices_map)
    assert timestamps[0] == datetime(2026, 11, 14, 23, 0, tzinfo=timezone.utc)
    assert prices_map[timestamps[0]] == 0.2


def test_hourly_estimation_always_on() -> None:
    contract = make_contract()
    curve = prices.zero_month_curve(contract, 2026, 11)
    for point in curve.points:
        point.price = 0.2
    device = Device(
        id=1,
        name="Nevera",
        category="fridge",
        mode="always_on",
        power_active_w=150,
        power_standby_w=0,
        duty_cycle_pct=35,
        annual_kwh=None,
        always_plugged=True,
        flexibility="none",
        enabled=True,
    )
    est = estimation.estimate_device_hourly(device, contract, curve, 2026, 11)
    assert est.energy_kwh > 0
    assert abs(est.cost_eur - est.energy_kwh * 0.2) < 0.01
    assert abs(sum(est.hourly.values()) - est.energy_kwh) < 0.01


def test_bill_applies_pepephone_service_discount() -> None:
    contract = make_contract(has_pepephone_discount=True)
    price = make_price()
    curve = prices.zero_month_curve(contract, 2026, 11)
    for point in curve.points:
        point.price = 0.2
    energy = {point.local_dt: 0.01 for point in curve.points[:100]}
    bill = tariff.bill_breakdown_hourly(contract, price, 30, energy, curve)
    assert bill["service_fee"] == 0
    assert bill["service_discount"] == 3.996196
    assert bill["fees_total"] < 3.0


def test_bill_applies_bono_social_only_to_pvpc() -> None:
    pvpc_contract = make_contract(
        profile_id="pvpc_2td",
        bono_social_category="vulnerable",
        bono_social_energy_limit_kwh=1587,
    )
    pvpc_price = make_price("pvpc_2td")
    pvpc_curve = prices.zero_month_curve(pvpc_contract, 2026, 11)
    for point in pvpc_curve.points:
        point.price = 0.2
    energy = {point.local_dt: 1.0 for point in pvpc_curve.points[:100]}
    pvpc_bill = tariff.bill_breakdown_hourly(pvpc_contract, pvpc_price, 30, energy, pvpc_curve)
    assert pvpc_bill["bono_social_applied"] is True
    assert pvpc_bill["bono_social_percentage"] == 0.425
    assert pvpc_bill["bono_social_discount"] > 0

    pepe_contract = make_contract(bono_social_category="vulnerable")
    pepe_price = make_price()
    pepe_curve = prices.zero_month_curve(pepe_contract, 2026, 11)
    for point in pepe_curve.points:
        point.price = 0.2
    pepe_bill = tariff.bill_breakdown_hourly(pepe_contract, pepe_price, 30, energy, pepe_curve)
    assert pepe_bill["bono_social_applied"] is False
    assert pepe_bill["bono_social_discount"] == 0


def test_pvpc_price_does_not_overwrite_pepe_month() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        contract = make_contract(profile_id="pvpc_2td")
        db.add(contract)
        pepe_price = TariffPrice(
            contract_id=1,
            valid_from=date(2026, 10, 1),
            valid_to=date(2026, 10, 31),
            month_label="Octubre 2026",
            source="pepe_api",
            status="confirmed",
            p1_price=0.4,
            p2_price=0.3,
            p3_price=0.2,
            power_p1_price=0.075903,
            power_p2_price=0.001987,
            service_fee_eur_month=3.996196,
            social_bond_eur_month=0.908639,
            vat_rate=0.21,
            electricity_tax_rate=0.0511269632,
        )
        db.add(pepe_price)
        db.commit()

        def fake_prices(*_args, **_kwargs):
            return {
                datetime(2026, 10, 1, 0, tzinfo=timezone.utc): 0.1,
                datetime(2026, 10, 1, 1, tzinfo=timezone.utc): 0.2,
            }, True

        original = pvpc.pvpc_month_prices
        pvpc.pvpc_month_prices = fake_prices
        try:
            pvpc_price = prices.ensure_tariff_price(db, contract, 2026, 10)
        finally:
            pvpc.pvpc_month_prices = original

        assert pvpc_price is not None
        assert pvpc_price.source == "ree_pvpc"
        stored = db.query(TariffPrice).filter_by(contract_id=1).all()
        assert len(stored) == 1
        assert stored[0].source == "pepe_api"
        assert stored[0].p1_price == 0.4
