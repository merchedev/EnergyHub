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
