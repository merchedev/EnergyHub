from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_health_and_empty_bootstrap() -> None:
    with TestClient(app) as client:
        client.post("/api/demo/reset")
        assert client.get("/api/health").status_code == 200
        bootstrap = client.get("/api/bootstrap").json()
        assert bootstrap["has_contract"] is False
        assert bootstrap["has_price"] is False


def test_contract_device_and_dashboard_flow() -> None:
    with TestClient(app) as client:
        client.post("/api/demo/reset")
        response = client.post(
            "/api/contract",
            json={
                "name": "Casa test",
                "provider": "Pepe Energy",
                "power_p1_kw": 4.6,
                "power_p2_kw": 4.6,
                "service_fee_eur_month": 3.996196,
                "social_bond_eur_month": 0.908639,
                "meter_rent_eur_month": 0.81,
                "vat_rate": 0.21,
                "electricity_tax_rate": 0.0511269632,
            },
        )
        assert response.status_code == 200
        price = client.post(
            "/api/tariff/prices",
            json={
                "month": "2026-10",
                "p1_price": 0.404644,
                "p2_price": 0.318715,
                "p3_price": 0.283266,
                "power_p1_price": 0.075903,
                "power_p2_price": 0.001987,
                "service_fee_eur_month": 3.996196,
                "social_bond_eur_month": 0.908639,
                "vat_rate": 0.21,
                "electricity_tax_rate": 0.0511269632,
            },
        )
        assert price.status_code == 200
        preview = client.post(
            "/api/devices/preview",
            json={
                "device": {
                    "name": "Vitro",
                    "category": "vitro",
                    "mode": "hours_per_day",
                    "power_active_w": 2000,
                    "power_standby_w": 0,
                    "duty_cycle_pct": 100,
                    "hours_per_day": 1,
                    "cycles_per_week": 0,
                    "minutes_per_cycle": 0,
                    "always_plugged": True,
                    "flexibility": "none",
                    "enabled": True,
                }
            },
        )
        assert preview.status_code == 200
        assert preview.json()["energy_kwh"] > 0
        assert preview.json()["price_available"] is True
        assert preview.json()["cost_eur"] > 0
        dashboard = client.get("/api/dashboard?month=2026-11")
        assert dashboard.status_code == 200
        assert dashboard.json()["price"]["is_fallback"] is True
        assert dashboard.json()["totals"]["total"] > 0


def test_pepe_profile_uses_manual_price_for_current_month() -> None:
    from datetime import date

    from app.database import SessionLocal
    from app.models import Contract
    from app.services import tariff

    with TestClient(app) as client:
        client.post("/api/demo/reset")
        assert (
            client.post(
                "/api/contract",
                json={
                    "name": "Casa Pepe",
                    "provider": "Pepe Energy",
                    "power_p1_kw": 4.6,
                    "power_p2_kw": 4.6,
                    "service_fee_eur_month": 3.996196,
                    "social_bond_eur_month": 0.908639,
                    "meter_rent_eur_month": 0.81,
                    "vat_rate": 0.21,
                    "electricity_tax_rate": 0.0511269632,
                },
            ).status_code
            == 200
        )
        with SessionLocal() as db:
            contract = db.query(Contract).one()
            tariff.upsert_price(
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
            )
        assert (
            client.post(
                "/api/tariff/prices",
                json={
                    "month": "2026-11",
                    "p1_price": 0.3,
                    "p2_price": 0.2,
                    "p3_price": 0.1,
                    "power_p1_price": 0.075903,
                    "power_p2_price": 0.001987,
                    "service_fee_eur_month": 3.996196,
                    "social_bond_eur_month": 0.908639,
                    "vat_rate": 0.21,
                    "electricity_tax_rate": 0.0511269632,
                },
            ).status_code
            == 200
        )

        dashboard = client.get("/api/dashboard?month=2026-11")
        assert dashboard.status_code == 200
        price = dashboard.json()["price"]
        assert price["is_fallback"] is False
        assert price["source"] == "manual"
        assert abs(price["p1_price"] - 0.3) < 0.001

        preview = client.post(
            "/api/devices/preview",
            json={
                "device": {
                    "name": "Vitro",
                    "category": "vitro",
                    "mode": "hours_per_day",
                    "power_active_w": 2000,
                    "power_standby_w": 0,
                    "duty_cycle_pct": 100,
                    "hours_per_day": 1,
                    "cycles_per_week": 0,
                    "minutes_per_cycle": 0,
                    "always_plugged": True,
                    "flexibility": "none",
                    "enabled": True,
                }
            },
        )
        assert preview.status_code == 200
        assert preview.json()["price_is_fallback"] is False


def test_device_preview_without_price_is_explicit() -> None:
    with TestClient(app) as client:
        client.post("/api/demo/reset")
        contract = client.post(
            "/api/contract",
            json={
                "name": "Casa sin precios",
                "provider": "Pepe Energy",
                "power_p1_kw": 4.6,
                "power_p2_kw": 4.6,
                "service_fee_eur_month": 3.996196,
                "social_bond_eur_month": 0.908639,
                "meter_rent_eur_month": 0.81,
                "vat_rate": 0.21,
                "electricity_tax_rate": 0.0511269632,
            },
        )
        assert contract.status_code == 200
        preview = client.post(
            "/api/devices/preview",
            json={
                "device": {
                    "name": "Nevera EVVO F90X AQUA",
                    "category": "fridge",
                    "mode": "always_on",
                    "power_active_w": 150,
                    "power_standby_w": 0,
                    "duty_cycle_pct": 35,
                    "annual_kwh": 257,
                    "hours_per_day": 0,
                    "cycles_per_week": 0,
                    "minutes_per_cycle": 0,
                    "always_plugged": True,
                    "flexibility": "none",
                    "enabled": True,
                }
            },
        )
        assert preview.status_code == 200
        data = preview.json()
        assert data["energy_kwh"] > 0
        assert data["price_available"] is False
        assert data["cost_eur"] == 0
        assert data["price_month_label"]


def test_device_hourly_returns_profile_and_top_period() -> None:
    import json
    from datetime import date

    from app.database import SessionLocal
    from app.models import DeviceEnergyReading

    with TestClient(app) as client:
        client.post("/api/demo/reset")
        assert (
            client.post(
                "/api/contract",
                json={
                    "name": "Casa horaria",
                    "provider": "Pepe Energy",
                    "power_p1_kw": 4.6,
                    "power_p2_kw": 4.6,
                    "service_fee_eur_month": 3.996196,
                    "social_bond_eur_month": 0.908639,
                    "meter_rent_eur_month": 0.81,
                    "vat_rate": 0.21,
                    "electricity_tax_rate": 0.0511269632,
                },
            ).status_code
            == 200
        )
        assert (
            client.post(
                "/api/tariff/prices",
                json={
                    "month": "2026-11",
                    "p1_price": 0.3,
                    "p2_price": 0.2,
                    "p3_price": 0.1,
                    "power_p1_price": 0.075903,
                    "power_p2_price": 0.001987,
                    "service_fee_eur_month": 3.996196,
                    "social_bond_eur_month": 0.908639,
                    "vat_rate": 0.21,
                    "electricity_tax_rate": 0.0511269632,
                },
            ).status_code
            == 200
        )
        device_response = client.post(
            "/api/devices",
            json={
                "name": "Lavadora Samsung",
                "category": "washing_machine",
                "mode": "entity",
                "power_active_w": 600,
                "power_standby_w": 0.5,
                "duty_cycle_pct": 100,
                "hours_per_day": 1,
                "cycles_per_week": 0,
                "minutes_per_cycle": 0,
                "always_plugged": True,
                "flexibility": "flexible",
                "entity_id": "switch.lavadora",
                "energy_entity_id": "sensor.lavadora_energia",
                "enabled": True,
            },
        )
        assert device_response.status_code == 200
        device_id = device_response.json()["device"]["id"]
        with SessionLocal() as db:
            db.add(
                DeviceEnergyReading(
                    device_id=device_id,
                    period_start=date(2026, 11, 1),
                    energy_kwh=8.0,
                    source="ha_energy_sensor",
                    hourly_json=json.dumps(
                        {
                            "2026-11-14T13:00:00+01:00": 5.0,
                            "2026-11-14T14:00:00+01:00": 3.0,
                        }
                    ),
                )
            )
            db.commit()

        response = client.get(f"/api/devices/{device_id}/hourly?month=2026-11")
        assert response.status_code == 200
        data = response.json()
        assert data["energy_resolution"] == "hourly"
        assert abs(data["energy_kwh"] - 8.0) < 0.01
        assert len(data["profile"]) == 24
        assert len(data["periods"]) == 3
        assert data["top_period"]["id"] == "P3"
        assert abs(data["top_period"]["share"] - 100.0) < 0.01
        assert data["top_hour"]["hour"] == 13
        assert data["top_day"]["date"] == "2026-11-14"
        assert len(data["days"]) == 1
        assert len(data["hours"]) == 2
        assert data["price_is_fallback"] is False
        assert abs(data["periods"][2]["cost_eur"] - 0.8) < 0.01


def test_dashboard_uses_stored_ha_energy_reading() -> None:
    from datetime import date

    from app.database import SessionLocal
    from app.models import Device, DeviceEnergyReading

    with TestClient(app) as client:
        client.post("/api/demo/reset")
        assert client.post(
            "/api/contract",
            json={
                "name": "Casa HA",
                "provider": "Pepe Energy",
                "power_p1_kw": 4.6,
                "power_p2_kw": 4.6,
                "service_fee_eur_month": 3.996196,
                "social_bond_eur_month": 0.908639,
                "meter_rent_eur_month": 0.81,
                "vat_rate": 0.21,
                "electricity_tax_rate": 0.0511269632,
            },
        ).status_code == 200
        assert client.post(
            "/api/tariff/prices",
            json={
                "month": "2026-11",
                "p1_price": 0.3,
                "p2_price": 0.2,
                "p3_price": 0.1,
                "power_p1_price": 0.075903,
                "power_p2_price": 0.001987,
                "service_fee_eur_month": 3.996196,
                "social_bond_eur_month": 0.908639,
                "vat_rate": 0.21,
                "electricity_tax_rate": 0.0511269632,
            },
        ).status_code == 200
        device_response = client.post(
            "/api/devices",
            json={
                "name": "Lavadora Samsung",
                "category": "washing_machine",
                "mode": "entity",
                "power_active_w": 600,
                "power_standby_w": 0.5,
                "duty_cycle_pct": 100,
                "hours_per_day": 1,
                "cycles_per_week": 0,
                "minutes_per_cycle": 0,
                "always_plugged": True,
                "flexibility": "flexible",
                "entity_id": "switch.lavadora",
                "energy_entity_id": "sensor.lavadora_energy",
                "enabled": True,
            },
        )
        assert device_response.status_code == 200
        device_id = device_response.json()["device"]["id"]
        with SessionLocal() as db:
            db.add(
                DeviceEnergyReading(
                    device_id=device_id,
                    period_start=date(2026, 11, 1),
                    energy_kwh=25.0,
                    source="ha_energy_sensor",
                )
            )
            db.commit()
            assert db.query(Device).count() == 1

        dashboard = client.get("/api/dashboard?month=2026-11")
        assert dashboard.status_code == 200
        data = dashboard.json()
        assert abs(data["totals"]["energy_kwh"] - 25.0) < 0.01
        assert data["devices"][0]["energy_source"] == "ha_energy_sensor"
        assert data["devices"][0]["energy_resolution"] == "monthly"
