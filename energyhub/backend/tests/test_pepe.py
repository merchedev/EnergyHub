from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from app.services.pepe import parse_pepe_payload


def test_parse_pepe_fixture() -> None:
    path = Path(__file__).parent / "fixtures" / "pepe_last_month.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    offer = parse_pepe_payload(payload)
    assert offer.valid_from == date(2026, 10, 1)
    assert offer.month_label == "Octubre 2026"
    assert offer.p1_price == 0.404644
    assert offer.p2_price == 0.318715
    assert offer.p3_price == 0.283266
    assert offer.power_p1_price == 0.075903
    assert offer.power_p2_price == 0.001987
    assert offer.service_fee_eur_month is not None
    assert offer.social_bond_eur_month is not None


def test_parse_pepe_rejects_bad_payload() -> None:
    import pytest

    from app.services.pepe import PepeFetchError

    with pytest.raises(PepeFetchError):
        parse_pepe_payload({"foo": "bar"})


def test_parse_pepe_fixed_tariff() -> None:
    payload = {
        "fixed": {
            "type": "electricity",
            "kind": "fixed",
            "variant": "E_SALE_FIXED_PRICE_SERVICE_FEE_TELCO_DISCOUNT_24H_POWER_2026_10_01",
            "energyPrices": [0.1199],
            "powerPrices": [0.075903, 0.001987],
            "generalVatTaxRate": 0.21,
            "electricityTaxRate": 0.0511269632,
            "serviceFeePriceTaxIncluded": 3.996196,
            "socialBond": {"serviceFeePriceTaxIncluded": 0.908639},
            "lastUpdatedMonthName": "Octubre 2026",
        }
    }
    offer = parse_pepe_payload(payload, kind="fixed")
    assert offer.p1_price == offer.p2_price == offer.p3_price == 0.1199
    assert offer.month_label == "Octubre 2026"
