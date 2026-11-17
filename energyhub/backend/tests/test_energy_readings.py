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
        return [
            {"start": "2026-01-01T00:00:00+00:00", "change": 12.5},
            {"start": "2026-01-01T01:00:00+00:00", "change": 7.5},
        ]


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
    assert result.hourly is not None
    assert abs(sum(result.hourly.values()) - 20.0) < 0.01


class FakeStatsEpochMsHaClient(FakeHaClient):
    """Home Assistant returns statistics timestamps as epoch milliseconds."""

    async def get_statistics(self, _entity_id: str, _start, _end, period: str = "hour"):
        assert period == "hour"
        return [
            {"start": 1767225600000, "end": 1767229200000, "change": 12.5},
            {"start": 1767229200000, "end": 1767232800000, "change": 7.5},
        ]


async def test_fetch_month_energy_parses_statistics_epoch_milliseconds() -> None:
    client = FakeStatsEpochMsHaClient(energy_state(), [])
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
    assert result.hourly is not None
    assert len(result.hourly) == 2
    assert abs(sum(result.hourly.values()) - 20.0) < 0.01
    assert sorted(hour.hour for hour in result.hourly) == [1, 2]


async def test_fetch_month_energy_builds_hourly_from_history() -> None:
    history = [
        (datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc), 100.0),
        (datetime(2026, 1, 1, 0, 30, tzinfo=timezone.utc), 105.0),
        (datetime(2026, 1, 1, 1, 15, tzinfo=timezone.utc), 110.0),
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
    assert result.energy_kwh == 10.0
    assert result.hourly is not None
    assert abs(sum(result.hourly.values()) - 10.0) < 0.01
    assert len(result.hourly) == 2


async def test_fetch_month_energy_handles_daily_resets_in_history() -> None:
    history = [
        (datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc), 100.0),
        (datetime(2026, 1, 2, 0, 0, tzinfo=timezone.utc), 0.5),
        (datetime(2026, 1, 2, 1, 0, tzinfo=timezone.utc), 1.5),
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
    assert result.energy_kwh == 1.5
    assert result.hourly is not None
