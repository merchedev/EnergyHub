from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Calibration, Contract, TariffPrice
from .periods import PERIOD_NAMES, PERIOD_ORDER, month_bounds


class NoPriceError(Exception):
    pass


def get_active_contract(db: Session) -> Contract | None:
    return db.scalars(
        select(Contract).where(Contract.is_active.is_(True)).order_by(Contract.id.desc())
    ).first()


def get_price_for_month(
    db: Session, contract: Contract, year: int, month: int
) -> tuple[TariffPrice | None, bool]:
    first, last = month_bounds(year, month)
    price = db.scalars(
        select(TariffPrice)
        .where(
            TariffPrice.contract_id == contract.id,
            TariffPrice.valid_from <= last,
        )
        .order_by(TariffPrice.valid_from.desc())
    ).first()
    if price is None:
        return None, False
    is_fallback = not (price.valid_from.year == year and price.valid_from.month == month)
    return price, is_fallback


def get_latest_calibration(db: Session, contract: Contract) -> Calibration | None:
    return db.scalars(
        select(Calibration)
        .where(Calibration.contract_id == contract.id)
        .order_by(Calibration.created_at.desc(), Calibration.id.desc())
    ).first()


def calibration_factor(db: Session, contract: Contract) -> float:
    calibration = get_latest_calibration(db, contract)
    if calibration is None:
        return 1.0
    return max(0.25, min(4.0, float(calibration.factor or 1.0)))


def period_prices(price: TariffPrice) -> dict[str, float]:
    return {"P1": price.p1_price, "P2": price.p2_price, "P3": price.p3_price}


def period_price_list(price: TariffPrice | None) -> list[dict]:
    if price is None:
        return [
            {"id": p, "name": PERIOD_NAMES[p], "price": 0.0}
            for p in PERIOD_ORDER
        ]
    values = period_prices(price)
    return [{"id": p, "name": PERIOD_NAMES[p], "price": values[p]} for p in PERIOD_ORDER]


def effective_vat_rate(contract: Contract, price: TariffPrice | None) -> float:
    if price is not None and price.vat_rate is not None:
        return float(price.vat_rate)
    return float(contract.vat_rate)


def effective_electricity_tax_rate(contract: Contract, price: TariffPrice | None) -> float:
    if price is not None and price.electricity_tax_rate is not None:
        return float(price.electricity_tax_rate)
    return float(contract.electricity_tax_rate)


def effective_fees(contract: Contract, price: TariffPrice | None) -> dict[str, float]:
    service_fee = (
        float(price.service_fee_eur_month)
        if price is not None and price.service_fee_eur_month is not None
        else float(contract.service_fee_eur_month)
    )
    social_bond = (
        float(price.social_bond_eur_month)
        if price is not None and price.social_bond_eur_month is not None
        else float(contract.social_bond_eur_month)
    )
    return {
        "service_fee": service_fee,
        "social_bond": social_bond,
        "meter_rent": float(contract.meter_rent_eur_month),
        "other_fees": float(contract.other_fees_eur_month),
    }


def bill_breakdown(
    contract: Contract,
    price: TariffPrice | None,
    days: int,
    energy_by_period: dict[str, float],
) -> dict:
    if price is None:
        raise NoPriceError("No hay precios de energía para este mes")
    values = period_prices(price)
    energy_kwh = sum(max(0.0, float(energy_by_period.get(p, 0.0))) for p in PERIOD_ORDER)
    energy_cost = sum(max(0.0, float(energy_by_period.get(p, 0.0))) * values[p] for p in PERIOD_ORDER)
    power_cost = (
        float(contract.power_p1_kw) * float(price.power_p1_price)
        + float(contract.power_p2_kw) * float(price.power_p2_price)
    ) * max(0, days)
    fees = effective_fees(contract, price)
    fees_total = sum(fees.values())
    tax_rate = effective_electricity_tax_rate(contract, price)
    vat_rate = effective_vat_rate(contract, price)
    taxable_base = energy_cost + power_cost
    electricity_tax = max(taxable_base * tax_rate, energy_kwh * 0.001)
    vat = (taxable_base + electricity_tax) * vat_rate
    total = taxable_base + electricity_tax + vat + fees_total
    return {
        "days": days,
        "energy_kwh": energy_kwh,
        "energy_cost": energy_cost,
        "power_cost": power_cost,
        "service_fee": fees["service_fee"],
        "social_bond": fees["social_bond"],
        "meter_rent": fees["meter_rent"],
        "other_fees": fees["other_fees"],
        "fees_total": fees_total,
        "electricity_tax": electricity_tax,
        "vat": vat,
        "taxable_base": taxable_base,
        "total": total,
        "energy_prices": values,
        "electricity_tax_rate": tax_rate,
        "vat_rate": vat_rate,
    }


def fixed_breakdown(contract: Contract, price: TariffPrice | None, days: int) -> dict:
    return bill_breakdown(contract, price, days, {"P1": 0.0, "P2": 0.0, "P3": 0.0})


def price_to_dict(
    price: TariffPrice | None,
    year: int,
    month: int,
    is_fallback: bool,
) -> dict | None:
    if price is None:
        return None
    return {
        "id": price.id,
        "month_label": price.month_label,
        "valid_from": price.valid_from.isoformat(),
        "valid_to": price.valid_to.isoformat() if price.valid_to else None,
        "source": price.source,
        "status": price.status,
        "is_fallback": is_fallback,
        "p1_price": price.p1_price,
        "p2_price": price.p2_price,
        "p3_price": price.p3_price,
        "power_p1_price": price.power_p1_price,
        "power_p2_price": price.power_p2_price,
        "service_fee_eur_month": price.service_fee_eur_month,
        "social_bond_eur_month": price.social_bond_eur_month,
        "vat_rate": price.vat_rate,
        "electricity_tax_rate": price.electricity_tax_rate,
        "periods": period_price_list(price),
        "reference_month": f"{price.valid_from.year:04d}-{price.valid_from.month:02d}",
        "requested_month": f"{year:04d}-{month:02d}",
    }


def upsert_price(
    db: Session,
    contract: Contract,
    valid_from: date,
    month_label: str,
    p1: float,
    p2: float,
    p3: float,
    power_p1: float,
    power_p2: float,
    service_fee: float | None = None,
    social_bond: float | None = None,
    vat_rate: float | None = None,
    electricity_tax_rate: float | None = None,
    source: str = "manual",
    status: str = "confirmed",
    raw_json: str | None = None,
    notes: str | None = None,
) -> TariffPrice:
    price = db.scalars(
        select(TariffPrice).where(
            TariffPrice.contract_id == contract.id,
            TariffPrice.valid_from == valid_from,
        )
    ).first()
    if price is None:
        price = TariffPrice(contract_id=contract.id, valid_from=valid_from)
        db.add(price)
    price.month_label = month_label
    price.valid_to = date(valid_from.year, valid_from.month, month_bounds(valid_from.year, valid_from.month)[1].day)
    price.p1_price = float(p1)
    price.p2_price = float(p2)
    price.p3_price = float(p3)
    price.power_p1_price = float(power_p1)
    price.power_p2_price = float(power_p2)
    price.service_fee_eur_month = service_fee
    price.social_bond_eur_month = social_bond
    price.vat_rate = vat_rate
    price.electricity_tax_rate = electricity_tax_rate
    price.source = source
    price.status = status
    price.raw_json = raw_json
    price.notes = notes
    db.commit()
    db.refresh(price)
    return price
