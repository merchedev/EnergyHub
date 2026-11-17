from __future__ import annotations

from datetime import datetime, timezone

from app.models import Contract
from app.services import energy_readings


class FakeHaClient:
    def __init__(self, state: dict, history: list[tuple[datetime, float]]):
        self.state = state
        self.history = history

    async def get_state(self, _entity_id: str) -> dict:
        return self.state

    async def get_numeric_history(self, _entity_id: str, _start, _end):
        return self.history


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


def energy_state(unit: str = "kWh", state_class: str = "total_increasing") -> dict:
    return {
        "state": "150",
        "attributes": {
            "unit_of_measurement": unit,
            "device_class": "energy",
            "state_class": state_class,
        },
    }


async def test_fetch_month_energy_uses_start_and_end_readings() -> None:
    history = [
        (datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc), 100.0),
        (datetime(2026, 1, 31, 23, 0, tzinfo=timezone.utc), 150.0),
    ]
    client = FakeHaClient(energy_state(), history)
    result = await energy_readings.fetch_month_energy(
        client,  # type: ignore[arg-type]
        make_contract(),
        "sensor.lavadora_energy",
        2026,
        1,
        now=datetime(2026, 2, 15, tzinfo=timezone.utc),
    )
    assert result.error is None
    assert result.energy_kwh == 50.0
    assert result.unit == "kWh"


async def test_fetch_month_energy_converts_wh() -> None:
    history = [
        (datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc), 100000.0),
        (datetime(2026, 1, 31, 23, 0, tzinfo=timezone.utc), 150000.0),
    ]
    client = FakeHaClient(energy_state(unit="Wh"), history)
    result = await energy_readings.fetch_month_energy(
        client,  # type: ignore[arg-type]
        make_contract(),
        "sensor.lavadora_energy",
        2026,
        1,
        now=datetime(2026, 2, 15, tzinfo=timezone.utc),
    )
    assert result.error is None
    assert result.energy_kwh == 50.0


async def test_fetch_month_energy_rejects_instantaneous_sensor() -> None:
    client = FakeHaClient(energy_state(state_class="measurement"), [])
    result = await energy_readings.fetch_month_energy(
        client,  # type: ignore[arg-type]
        make_contract(),
        "sensor.lavadora_power",
        2026,
        1,
        now=datetime(2026, 2, 15, tzinfo=timezone.utc),
    )
    assert result.energy_kwh is None
    assert "medición instantánea" in (result.error or "")


async def test_fetch_month_energy_rejects_negative_delta() -> None:
    history = [
        (datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc), 150.0),
        (datetime(2026, 1, 31, 23, 0, tzinfo=timezone.utc), 100.0),
    ]
    client = FakeHaClient(energy_state(), history)
    result = await energy_readings.fetch_month_energy(
        client,  # type: ignore[arg-type]
        make_contract(),
        "sensor.lavadora_energy",
        2026,
        1,
        now=datetime(2026, 2, 15, tzinfo=timezone.utc),
    )
    assert result.energy_kwh is None
    assert "reinicio" in (result.error or "")


class FakeConfiguredHaClient(FakeHaClient):
    configured = True


async def test_refresh_readings_stores_month_energy_and_skips_complete_month() -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.database import Base
    from app.models import Device, DeviceEnergyReading

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    history = [
        (datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc), 100.0),
        (datetime(2026, 1, 31, 23, 0, tzinfo=timezone.utc), 150.0),
    ]
    client = FakeConfiguredHaClient(energy_state(), history)
    with Session(engine) as db:
        contract = make_contract()
        db.add(contract)
        device = Device(
            id=1,
            name="Lavadora Samsung",
            category="washing_machine",
            mode="entity",
            energy_entity_id="sensor.refresh_test_energy",
            enabled=True,
        )
        db.add(device)
        db.commit()

        updated = await energy_readings.refresh_readings(
            db, client, contract, [device], 2026, 1
        )
        assert updated == 1
        row = db.query(DeviceEnergyReading).one()
        assert row.energy_kwh == 50.0
        assert row.source == "ha_energy_sensor"
        assert row.unit == "kWh"

        skipped = await energy_readings.refresh_readings(
            db, client, contract, [device], 2026, 1
        )
        assert skipped == 0


class FakeStatsHaClient(FakeHaClient):
    async def get_statistics(self, _entity_id: str, _start, _end, period: str = "hour"):
        assert period == "hour"
        return [{"change": 12.5}, {"change": 7.5}]


async def test_fetch_month_energy_prefers_long_term_statistics() -> None:
    client = FakeStatsHaClient(energy_state(), [])
    result = await energy_readings.fetch_month_energy(
        client,  # type: ignore[arg-type]
        make_contract(),
        "sensor.lavadora_energy",
        2026,
        1,
        now=datetime(2026, 2, 15, tzinfo=timezone.utc),
    )
    assert result.error is None
    assert result.energy_kwh == 20.0
