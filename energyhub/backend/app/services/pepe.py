from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

import httpx

from ..config import PEPE_API_URL, PEPE_TIMEOUT_SECONDS
from .periods import parse_spanish_month


class PepeFetchError(Exception):
    pass


@dataclass
class PepeOffer:
    month_label: str
    valid_from: date
    p1_price: float
    p2_price: float
    p3_price: float
    power_p1_price: float
    power_p2_price: float
    service_fee_eur_month: float | None
    social_bond_eur_month: float | None
    vat_rate: float | None
    electricity_tax_rate: float | None
    raw_json: str
    fetched_at: datetime


def _to_float(value: Any, fallback: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def parse_pepe_payload(
    payload: dict[str, Any],
    fetched_at: datetime | None = None,
    kind: str = "variable",
) -> PepeOffer:
    if not isinstance(payload, dict):
        raise PepeFetchError("La respuesta de Pepe no es un objeto JSON válido")

    if "energyPrices" in payload:
        offer: dict[str, Any] = payload
    else:
        candidates = [
            value
            for value in payload.values()
            if isinstance(value, dict)
            and value.get("type") == "electricity"
            and value.get("kind") == kind
        ]
        if not candidates:
            raise PepeFetchError(f"No se ha encontrado la tarifa {kind} de Pepe en la respuesta")
        if kind == "variable":
            indexed = [item for item in candidates if "INDEXED" in str(item.get("variant", "")).upper()]
            offer = (indexed or candidates)[0]
        else:
            fixed = [item for item in candidates if "FIXED" in str(item.get("variant", "")).upper()]
            offer = (fixed or candidates)[0]

    energy_prices = offer.get("energyPrices") or []
    if not isinstance(energy_prices, list) or not energy_prices:
        raise PepeFetchError("La respuesta de Pepe no incluye precios de energía")
    if len(energy_prices) < 3:
        # Tarifa de precio fijo: un único precio para todas las horas.
        fixed_price = _to_float(energy_prices[0])
        p1 = p2 = p3 = fixed_price
    else:
        p1 = _to_float(energy_prices[0])
        p2 = _to_float(energy_prices[1])
        p3 = _to_float(energy_prices[2])
    if min(p1, p2, p3) <= 0:
        raise PepeFetchError("Los precios de energía recibidos no son válidos")

    power_prices = offer.get("powerPrices") or []
    power_p1 = _to_float(power_prices[0]) if len(power_prices) >= 1 else 0.0
    power_p2 = _to_float(power_prices[1]) if len(power_prices) >= 2 else 0.0

    month_label = str(offer.get("lastUpdatedMonthName") or "").strip()
    valid_from = parse_spanish_month(month_label)

    service_fee = offer.get("serviceFeePriceTaxIncluded")
    if service_fee is None:
        service_fee = offer.get("serviceFeePrice")
    social_bond_obj = offer.get("socialBond") or {}
    social_bond = social_bond_obj.get("serviceFeePriceTaxIncluded")
    if social_bond is None:
        social_bond = social_bond_obj.get("serviceFeePrice")

    vat_rate = offer.get("generalVatTaxRate")
    electricity_tax_rate = offer.get("electricityTaxRate")

    return PepeOffer(
        month_label=month_label or f"{valid_from:%m/%Y}",
        valid_from=valid_from,
        p1_price=p1,
        p2_price=p2,
        p3_price=p3,
        power_p1_price=power_p1,
        power_p2_price=power_p2,
        service_fee_eur_month=_to_float(service_fee) if service_fee is not None else None,
        social_bond_eur_month=_to_float(social_bond) if social_bond is not None else None,
        vat_rate=_to_float(vat_rate) if vat_rate is not None else None,
        electricity_tax_rate=_to_float(electricity_tax_rate) if electricity_tax_rate is not None else None,
        raw_json=json.dumps(offer, ensure_ascii=False),
        fetched_at=fetched_at or datetime.now(timezone.utc),
    )


async def fetch_pepe_last_month(kind: str = "variable") -> PepeOffer:
    headers = {
        "Accept": "application/json",
        "Accept-Language": "es",
        "User-Agent": "EnergyHub/0.1 (Home Assistant energy estimator)",
    }
    try:
        async with httpx.AsyncClient(timeout=PEPE_TIMEOUT_SECONDS, follow_redirects=True) as client:
            response = await client.get(PEPE_API_URL, headers=headers)
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPStatusError as exc:
        raise PepeFetchError(f"Pepe ha respondido con HTTP {exc.response.status_code}") from exc
    except httpx.HTTPError as exc:
        raise PepeFetchError(f"No se ha podido consultar la API de Pepe: {exc}") from exc
    except ValueError as exc:
        raise PepeFetchError("La API de Pepe no ha devuelto JSON válido") from exc

    return parse_pepe_payload(payload, kind=kind)
