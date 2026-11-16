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
        dashboard = client.get("/api/dashboard?month=2026-11")
        assert dashboard.status_code == 200
        assert dashboard.json()["price"]["is_fallback"] is True
        assert dashboard.json()["totals"]["total"] > 0
