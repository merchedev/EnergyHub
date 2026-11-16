from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Contract, TariffPrice
from . import periods, profiles, pvpc


@dataclass
class PricePoint:
    local_dt: datetime
    utc_dt: datetime
    price: float
    period: str
    missing: bool = False

    def as_dict(self) -> dict:
        return {
            "timestamp": self.local_dt.isoformat(),
            "price": self.price,
            "period": self.period,
            "missing": self.missing,
        }


@dataclass
class PriceCurve:
    points: list[PricePoint]
    missing_hours: int
    source: str
    coverage: float

    def as_dict(self) -> dict:
        return {
            "points": [point.as_dict() for point in self.points],
            "missing_hours": self.missing_hours,
            "source": self.source,
            "coverage": self.coverage,
        }


def _tz(contract: Contract) -> ZoneInfo:
    try:
        return ZoneInfo(contract.timezone or "Europe/Madrid")
    except Exception:
        return ZoneInfo("Europe/Madrid")


def _month_bounds(year: int, month: int, tz: ZoneInfo) -> tuple[datetime, datetime]:
    start = datetime(year, month, 1, tzinfo=tz)
    if month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=tz)
    else:
        end = datetime(year, month + 1, 1, tzinfo=tz)
    return start, end


def zero_month_curve(contract: Contract, year: int, month: int) -> PriceCurve:
    tz = _tz(contract)
    start, end = _month_bounds(year, month, tz)
    points: list[PricePoint] = []
    current = start.astimezone(timezone.utc)
    end_utc = end.astimezone(timezone.utc)
    while current < end_utc:
        local = current.astimezone(tz).replace(minute=0, second=0, microsecond=0)
        points.append(
            PricePoint(
                local_dt=local,
                utc_dt=current,
                price=0.0,
                period=periods.period_for_datetime(local, contract.country, contract.region),
            )
        )
        current += timedelta(hours=1)
    return PriceCurve(points=points, missing_hours=len(points), source="none", coverage=0.0)


def ensure_tariff_price(db: Session, contract: Contract, year: int, month: int) -> TariffPrice | None:
    """Pepe uses stored monthly prices; PVPC gets a synthetic monthly price row."""
    from . import tariff

    profile = profiles.get_profile(contract.tariff_profile_id)
    if profile.get("price_source") != "ree_pvpc":
        if str(profile.get("price_source", "")).startswith("pepe_api"):
            existing, _ = tariff.get_price_for_month(
                db, contract, year, month, source="pepe_api"
            )
            if existing is not None:
                return existing
        existing, _ = tariff.get_price_for_month(db, contract, year, month, source="manual")
        return existing
    first, last = periods.month_bounds(year, month)
    row = db.scalars(
        select(TariffPrice).where(
            TariffPrice.contract_id == contract.id,
            TariffPrice.valid_from == first,
        )
    ).first()
    if row is None:
        row = TariffPrice(
            contract_id=contract.id,
            valid_from=first,
            valid_to=last,
            month_label=periods.month_label_short(year, month),
            source="ree_pvpc",
            status="confirmed",
            p1_price=0.0,
            p2_price=0.0,
            p3_price=0.0,
            power_p1_price=float(profile.get("power_p1_price") or 0.0),
            power_p2_price=float(profile.get("power_p2_price") or 0.0),
            service_fee_eur_month=float(profile.get("service_fee_eur_month") or 0.0),
            social_bond_eur_month=float(profile.get("social_bond_eur_month") or 0.0),
            vat_rate=float(profile.get("vat_rate") or 0.21),
            electricity_tax_rate=float(profile.get("electricity_tax_rate") or 0.0511269632),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
    try:
        prices, _ = pvpc.pvpc_month_prices(db, contract, year, month)
    except pvpc.PvpcError:
        return row
    if not prices:
        return row
    sums = {"P1": [0.0, 0.0], "P2": [0.0, 0.0], "P3": [0.0, 0.0]}
    for local_dt, price in prices.items():
        period = periods.period_for_datetime(local_dt, contract.country, contract.region)
        sums[period][0] += price
        sums[period][1] += 1
    row.p1_price = sums["P1"][0] / sums["P1"][1] if sums["P1"][1] else 0.0
    row.p2_price = sums["P2"][0] / sums["P2"][1] if sums["P2"][1] else 0.0
    row.p3_price = sums["P3"][0] / sums["P3"][1] if sums["P3"][1] else 0.0
    row.power_p1_price = float(profile.get("power_p1_price") or row.power_p1_price)
    row.power_p2_price = float(profile.get("power_p2_price") or row.power_p2_price)
    row.service_fee_eur_month = float(profile.get("service_fee_eur_month") or 0.0)
    row.social_bond_eur_month = float(profile.get("social_bond_eur_month") or 0.0)
    row.vat_rate = float(profile.get("vat_rate") or 0.21)
    row.electricity_tax_rate = float(profile.get("electricity_tax_rate") or 0.0511269632)
    db.commit()
    db.refresh(row)
    return row


def _hourly_map(
    db: Session,
    contract: Contract,
    year: int,
    month: int,
) -> tuple[dict[datetime, float], int, int]:
    prices, _ = pvpc.pvpc_month_prices(db, contract, year, month)
    return prices, len(prices), periods.month_days(year, month) * 24


def build_month_curve(
    db: Session,
    contract: Contract,
    price: TariffPrice,
    year: int,
    month: int,
    fill_missing: bool = True,
) -> PriceCurve:
    tz = _tz(contract)
    profile = profiles.get_profile(contract.tariff_profile_id)
    start, end = _month_bounds(year, month, tz)
    points: list[PricePoint] = []
    missing_hours = 0
    if profile.get("price_source") == "ree_pvpc":
        hourly, available, expected = _hourly_map(db, contract, year, month)
        fallback = sum(hourly.values()) / len(hourly) if hourly else 0.0
        current = start.astimezone(timezone.utc)
        end_utc = end.astimezone(timezone.utc)
        while current < end_utc:
            local = current.astimezone(tz).replace(minute=0, second=0, microsecond=0)
            price_value = hourly.get(local)
            missing = price_value is None
            if price_value is None:
                missing_hours += 1
                price_value = fallback if fill_missing else 0.0
            points.append(
                PricePoint(
                    local_dt=local,
                    utc_dt=current,
                    price=price_value,
                    period=periods.period_for_datetime(local, contract.country, contract.region),
                    missing=missing,
                )
            )
            current += timedelta(hours=1)
        coverage = min(1.0, available / expected) if expected else 0.0
        return PriceCurve(points=points, missing_hours=missing_hours, source="ree_pvpc", coverage=coverage)
    values = {"P1": price.p1_price, "P2": price.p2_price, "P3": price.p3_price}
    current = start.astimezone(timezone.utc)
    end_utc = end.astimezone(timezone.utc)
    while current < end_utc:
        local = current.astimezone(tz).replace(minute=0, second=0, microsecond=0)
        period = periods.period_for_datetime(local, contract.country, contract.region)
        points.append(
            PricePoint(
                local_dt=local,
                utc_dt=current,
                price=values.get(period, price.p3_price),
                period=period,
            )
        )
        current += timedelta(hours=1)
    return PriceCurve(points=points, missing_hours=0, source="period", coverage=1.0)


def build_range_curve(
    db: Session,
    contract: Contract,
    price: TariffPrice,
    start_local: datetime,
    end_local: datetime,
) -> PriceCurve:
    tz = _tz(contract)
    profile = profiles.get_profile(contract.tariff_profile_id)
    points: list[PricePoint] = []
    missing_hours = 0
    if profile.get("price_source") == "ree_pvpc":
        try:
            hourly, _ = pvpc.pvpc_price_map_for_range(db, contract, start_local, end_local)
        except pvpc.PvpcError:
            hourly = {}
        fallback = sum(hourly.values()) / len(hourly) if hourly else 0.0
        current = start_local.astimezone(timezone.utc)
        end_utc = end_local.astimezone(timezone.utc)
        while current < end_utc:
            local = current.astimezone(tz).replace(minute=0, second=0, microsecond=0)
            price_value = hourly.get(local)
            missing = price_value is None
            if price_value is None:
                missing_hours += 1
                price_value = fallback
            points.append(
                PricePoint(
                    local_dt=local,
                    utc_dt=current,
                    price=price_value,
                    period=periods.period_for_datetime(local, contract.country, contract.region),
                    missing=missing,
                )
            )
            current += timedelta(hours=1)
        return PriceCurve(
            points=points,
            missing_hours=missing_hours,
            source="ree_pvpc",
            coverage=0.0 if missing_hours else 1.0,
        )
    values = {"P1": price.p1_price, "P2": price.p2_price, "P3": price.p3_price}
    current = start_local.astimezone(timezone.utc)
    end_utc = end_local.astimezone(timezone.utc)
    while current < end_utc:
        local = current.astimezone(tz).replace(minute=0, second=0, microsecond=0)
        period = periods.period_for_datetime(local, contract.country, contract.region)
        points.append(
            PricePoint(
                local_dt=local,
                utc_dt=current,
                price=values.get(period, price.p3_price),
                period=period,
            )
        )
        current += timedelta(hours=1)
    return PriceCurve(points=points, missing_hours=0, source="period", coverage=1.0)


def cheapest_windows(
    curve: PriceCurve,
    duration_hours: int = 2,
    count: int = 3,
) -> list[dict]:
    points = [point for point in curve.points if not point.missing]
    if not points or duration_hours <= 0:
        return []
    width = max(1, min(duration_hours, len(points)))
    candidates: list[dict] = []
    for index in range(0, len(points) - width + 1):
        window = points[index : index + width]
        average = sum(point.price for point in window) / width
        candidates.append(
            {
                "start": window[0].local_dt.isoformat(),
                "end": (window[-1].local_dt + timedelta(hours=1)).isoformat(),
                "average_price": average,
                "hours": width,
                "period": window[0].period,
            }
        )
    candidates.sort(key=lambda item: item["average_price"])
    return candidates[:count]
