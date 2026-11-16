from __future__ import annotations

import json
from pathlib import Path

BUILTIN_PROFILES: dict[str, dict] = {
    "pepe_variable": {
        "id": "pepe_variable",
        "company": "Pepe Energy",
        "name": "Tarifa Variable",
        "country": "ES",
        "kind": "period",
        "price_source": "pepe_api_variable",
        "access_toll": "2.0TD",
        "service_fee_eur_month": 3.996196,
        "social_bond_eur_month": 0.908639,
        "meter_rent_eur_month": 0.81,
        "vat_rate": 0.21,
        "electricity_tax_rate": 0.0511269632,
        "power_p1_price": 0.075903,
        "power_p2_price": 0.001987,
        "supports_pepephone_discount": True,
        "pepephone_service_fee_discount": 3.996196,
        "bono_social_eligible": False,
        "requires_manual_prices": False,
        "notes": "Precios mensuales de punta, llano y valle publicados por Pepe.",
        "source_url": "https://www.pepeenergy.com/tarifas-luz/tarifa-variable-luz",
        "last_updated": "2026-10-01",
    },
    "pepe_estable": {
        "id": "pepe_estable",
        "company": "Pepe Energy",
        "name": "Tarifa Estable",
        "country": "ES",
        "kind": "fixed",
        "price_source": "pepe_api_fixed",
        "access_toll": "2.0TD",
        "service_fee_eur_month": 3.996196,
        "social_bond_eur_month": 0.908639,
        "meter_rent_eur_month": 0.81,
        "vat_rate": 0.21,
        "electricity_tax_rate": 0.0511269632,
        "power_p1_price": 0.075903,
        "power_p2_price": 0.001987,
        "supports_pepephone_discount": True,
        "pepephone_service_fee_discount": 3.996196,
        "bono_social_eligible": False,
        "requires_manual_prices": False,
        "notes": "Precio fijo para todas las horas; se actualiza desde Pepe.",
        "source_url": "https://www.pepeenergy.com/tarifas-luz/tarifa-estable-luz",
        "last_updated": "2026-10-01",
    },
    "pvpc_2td": {
        "id": "pvpc_2td",
        "company": "PVPC",
        "name": "Precio Voluntario al Pequeño Consumidor · 2.0TD",
        "country": "ES",
        "kind": "hourly",
        "price_source": "ree_pvpc",
        "access_toll": "2.0TD",
        "service_fee_eur_month": 0.0,
        "social_bond_eur_month": 0.908639,
        "meter_rent_eur_month": 0.81,
        "vat_rate": 0.21,
        "electricity_tax_rate": 0.0511269632,
        "power_p1_price": 0.075903,
        "power_p2_price": 0.001987,
        "supports_pepephone_discount": False,
        "pepephone_service_fee_discount": 0.0,
        "bono_social_eligible": True,
        "requires_manual_prices": False,
        "notes": "Precio horario PVPC publicado por REE. El término de potencia es regulado y editable.",
        "source_url": "https://www.esios.ree.es/es/pvpc",
        "last_updated": "2026-11-16",
    },
    "manual": {
        "id": "manual",
        "company": "Otra compañía",
        "name": "Tarifa personalizada",
        "country": "ES",
        "kind": "period",
        "price_source": "manual",
        "access_toll": "2.0TD",
        "service_fee_eur_month": 0.0,
        "social_bond_eur_month": 0.908639,
        "meter_rent_eur_month": 0.81,
        "vat_rate": 0.21,
        "electricity_tax_rate": 0.0511269632,
        "power_p1_price": 0.075903,
        "power_p2_price": 0.001987,
        "supports_pepephone_discount": False,
        "pepephone_service_fee_discount": 0.0,
        "bono_social_eligible": False,
        "requires_manual_prices": True,
        "notes": "Introduce los precios de tu contrato o de tu factura.",
        "source_url": "",
        "last_updated": "2026-11-16",
    },
}


def _catalog_paths() -> list[Path]:
    here = Path(__file__).resolve()
    return [
        here.parents[2] / "tariffs" / "catalog.json",
        here.parents[3] / "tariffs" / "catalog.json",
    ]


def load_community_profiles() -> list[dict]:
    for path in _catalog_paths():
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        profiles = data.get("profiles") if isinstance(data, dict) else None
        if isinstance(profiles, list):
            return [profile for profile in profiles if isinstance(profile, dict) and profile.get("id")]
    return []


def all_profiles() -> list[dict]:
    merged = {profile_id: dict(profile) for profile_id, profile in BUILTIN_PROFILES.items()}
    for profile in load_community_profiles():
        profile_id = str(profile["id"])
        if profile_id not in merged:
            merged[profile_id] = profile
    return list(merged.values())


def get_profile(profile_id: str | None) -> dict:
    if profile_id and profile_id in BUILTIN_PROFILES:
        return dict(BUILTIN_PROFILES[profile_id])
    if profile_id:
        for profile in load_community_profiles():
            if profile.get("id") == profile_id:
                return dict(profile)
    return dict(BUILTIN_PROFILES["manual"])


def is_pvpc(profile_id: str | None) -> bool:
    return profile_id == "pvpc_2td" or get_profile(profile_id).get("price_source") == "ree_pvpc"


def is_pepe(profile_id: str | None) -> bool:
    return str(get_profile(profile_id).get("price_source", "")).startswith("pepe_api")


def profile_defaults(profile_id: str | None) -> dict:
    profile = get_profile(profile_id)
    return {
        "provider": profile.get("company") or "Otra compañía",
        "tariff_type": str(profile.get("kind") or "period"),
        "tariff_profile_id": str(profile.get("id") or "manual"),
        "access_toll": profile.get("access_toll") or "2.0TD",
        "service_fee_eur_month": float(profile.get("service_fee_eur_month") or 0.0),
        "social_bond_eur_month": float(profile.get("social_bond_eur_month") or 0.0),
        "meter_rent_eur_month": float(profile.get("meter_rent_eur_month") or 0.0),
        "vat_rate": float(profile.get("vat_rate") or 0.21),
        "electricity_tax_rate": float(profile.get("electricity_tax_rate") or 0.0511269632),
        "supports_pepephone_discount": bool(profile.get("supports_pepephone_discount")),
        "pepephone_service_fee_discount": float(
            profile.get("pepephone_service_fee_discount") or 0.0
        ),
        "bono_social_eligible": bool(profile.get("bono_social_eligible")),
        "requires_manual_prices": bool(profile.get("requires_manual_prices")),
        "kind": str(profile.get("kind") or "period"),
        "price_source": str(profile.get("price_source") or "manual"),
    }
