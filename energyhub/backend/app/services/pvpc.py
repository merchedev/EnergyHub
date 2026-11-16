from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Contract, HourlyPrice
from . import periods

REE_URL = "https://apidatos.ree.es/es/datos/mercados/precios-mercados-tiempo-real"
PVPC_SOURCE = "ree_pvpc"


class PvpcError(Exception):
    pass


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _month_range(year: int, month: int, tz: ZoneInfo) -> tuple[datetime, datetime]:
    start = datetime(year, month, 1, tzinfo=tz)
    if month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=tz)
    else:
        end = datetime(year, month + 1, 1, tzinfo=tz)
    return start, end


def _fetch_ree(start: datetime, end: datetime) -> dict[datetime, float]:
    # La API de REE rechaza un end_date exacto a las 00:00 del mes siguiente.
    query_end = end
    if end.hour == 0 and end.minute == 0 and end.second == 0 and end > start:
        query_end = end - timedelta(minutes=1)
    params = {
        "start_date": start.strftime("%Y-%m-%dT%H:%M"),
        "end_date": query_end.strftime("%Y-%m-%dT%H:%M"),
        "time_trunc": "hour",
    }
    headers = {
        "Accept": "application/json",
        "User-Agent": "EnergyHub/0.2 (Home Assistant energy estimator)",
    }
    try:
        with httpx.Client(timeout=20.0, follow_redirects=True) as client:
            response = client.get(REE_URL, params=params, headers=headers)
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPError as exc:
        raise PvpcError(f"No se ha podido consultar el PVPC en REE: {exc}") from exc
    except ValueError as exc:
        raise PvpcError("REE no ha devuelto JSON válido") from exc

    return parse_ree_payload(payload)


def parse_ree_payload(payload: dict) -> dict[datetime, float]:
    included = payload.get("included") if isinstance(payload, dict) else None
    if not isinstance(included, list):
        raise PvpcError("REE no ha devuelto la serie PVPC")
    series = None
    for item in included:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "PVPC" or item.get("id") == "1001":
            series = item
            break
    if not series:
        raise PvpcError("No se ha encontrado el indicador PVPC en la respuesta de REE")
    values = (series.get("attributes") or {}).get("values") or []
    result: dict[datetime, float] = {}
    for value in values:
        if not isinstance(value, dict):
            continue
        raw_dt = value.get("datetime")
        raw_price = value.get("value")
        if raw_dt is None or raw_price is None:
            continue
        try:
            moment = datetime.fromisoformat(str(raw_dt).replace("Z", "+00:00"))
            price = float(raw_price) / 1000.0  # €/MWh -> €/kWh
        except (TypeError, ValueError):
            continue
        if price <= 0 or price > 2:
            continue
        result[moment.astimezone(timezone.utc)] = price
    if not result:
        raise PvpcError("REE no ha devuelto precios PVPC válidos")
    return result


def ensure_pvpc_prices(
    db: Session,
    contract: Contract,
    year: int,
    month: int,
    force: bool = False,
) -> tuple[dict[datetime, float], bool]:
    """Return UTC hourly PVPC prices for a month, fetching and caching if needed."""
    try:
        tz = ZoneInfo(contract.timezone or "Europe/Madrid")
    except Exception:
        tz = ZoneInfo("Europe/Madrid")
    start_local, end_local = _month_range(year, month, tz)
    start_utc = start_local.astimezone(timezone.utc)
    end_utc = end_local.astimezone(timezone.utc)
    existing_rows = list(
        db.scalars(
            select(HourlyPrice).where(
                HourlyPrice.source == PVPC_SOURCE,
                HourlyPrice.timestamp >= start_utc,
                HourlyPrice.timestamp < end_utc,
            )
        ).all()
    )
    latest_fetch = max((row.fetched_at for row in existing_rows), default=None)
    fresh = (
        latest_fetch is not None
        and _as_utc(latest_fetch) > datetime.now(timezone.utc) - timedelta(hours=6)
    )
    should_fetch = force or not existing_rows or not fresh
    if should_fetch:
        try:
            fetched = _fetch_ree(start_local, end_local)
        except PvpcError:
            if existing_rows:
                return {_as_utc(row.timestamp): row.price_eur_kwh for row in existing_rows}, False
            raise
        by_ts = {_as_utc(row.timestamp): row for row in existing_rows}
        for timestamp, price in fetched.items():
            row = by_ts.get(timestamp)
            if row is None:
                row = HourlyPrice(
                    source=PVPC_SOURCE,
                    timestamp=timestamp,
                    price_eur_kwh=price,
                    fetched_at=datetime.now(timezone.utc),
                )
                db.add(row)
            else:
                row.price_eur_kwh = price
                row.fetched_at = datetime.now(timezone.utc)
        db.commit()
        existing_rows = list(
            db.scalars(
                select(HourlyPrice).where(
                    HourlyPrice.source == PVPC_SOURCE,
                    HourlyPrice.timestamp >= start_utc,
                    HourlyPrice.timestamp < end_utc,
                )
            ).all()
        )
    return {_as_utc(row.timestamp): row.price_eur_kwh for row in existing_rows}, True


def pvpc_price_map_for_range(
    db: Session,
    contract: Contract,
    start_local: datetime,
    end_local: datetime,
    force: bool = False,
) -> tuple[dict[datetime, float], bool]:
    """Fetch PVPC prices for an arbitrary local range (e.g. next 48 h)."""
    try:
        tz = ZoneInfo(contract.timezone or "Europe/Madrid")
    except Exception:
        tz = ZoneInfo("Europe/Madrid")
    start_utc = start_local.astimezone(timezone.utc)
    end_utc = end_local.astimezone(timezone.utc)
    rows = list(
        db.scalars(
            select(HourlyPrice).where(
                HourlyPrice.source == PVPC_SOURCE,
                HourlyPrice.timestamp >= start_utc,
                HourlyPrice.timestamp < end_utc,
            )
        ).all()
    )
    should_fetch = force or not rows
    if should_fetch:
        try:
            fetched = _fetch_ree(start_local, end_local)
            by_ts = {_as_utc(row.timestamp): row for row in rows}
            for timestamp, price in fetched.items():
                row = by_ts.get(timestamp)
                if row is None:
                    db.add(
                        HourlyPrice(
                            source=PVPC_SOURCE,
                            timestamp=timestamp,
                            price_eur_kwh=price,
                            fetched_at=datetime.now(timezone.utc),
                        )
                    )
                else:
                    row.price_eur_kwh = price
            db.commit()
            rows = list(
                db.scalars(
                    select(HourlyPrice).where(
                        HourlyPrice.source == PVPC_SOURCE,
                        HourlyPrice.timestamp >= start_utc,
                        HourlyPrice.timestamp < end_utc,
                    )
                ).all()
            )
        except PvpcError:
            if not rows:
                raise
    return {_as_utc(row.timestamp).astimezone(tz): row.price_eur_kwh for row in rows}, True


def pvpc_month_prices(
    db: Session,
    contract: Contract,
    year: int,
    month: int,
    force: bool = False,
) -> tuple[dict[datetime, float], bool]:
    prices_utc, _ = ensure_pvpc_prices(db, contract, year, month, force=force)
    try:
        tz = ZoneInfo(contract.timezone or "Europe/Madrid")
    except Exception:
        tz = ZoneInfo("Europe/Madrid")
    return {_as_utc(timestamp).astimezone(tz): price for timestamp, price in prices_utc.items()}, True


def month_price_coverage(
    db: Session,
    contract: Contract,
    year: int,
    month: int,
) -> tuple[int, int]:
    try:
        tz = ZoneInfo(contract.timezone or "Europe/Madrid")
    except Exception:
        tz = ZoneInfo("Europe/Madrid")
    start, end = _month_range(year, month, tz)
    prices, _ = ensure_pvpc_prices(db, contract, year, month)
    expected = int((end.astimezone(timezone.utc) - start.astimezone(timezone.utc)).total_seconds() / 3600)
    return len(prices), expected


def current_pvpc_price(db: Session, contract: Contract) -> tuple[float | None, datetime | None]:
    now = datetime.now(timezone.utc)
    row = db.scalars(
        select(HourlyPrice)
        .where(HourlyPrice.source == PVPC_SOURCE, HourlyPrice.timestamp <= now)
        .order_by(HourlyPrice.timestamp.desc())
    ).first()
    if row is not None:
        return row.price_eur_kwh, _as_utc(row.timestamp)
    try:
        tz = ZoneInfo(contract.timezone or "Europe/Madrid")
    except Exception:
        tz = ZoneInfo("Europe/Madrid")
    local_now = now.astimezone(tz)
    prices, _ = pvpc_price_map_for_range(
        db,
        contract,
        local_now.replace(minute=0, second=0, microsecond=0),
        local_now + timedelta(hours=2),
    )
    for timestamp, price in sorted(prices.items()):
        if timestamp <= local_now:
            return price, timestamp
    return None, None


def month_has_complete_data(year: int, month: int, prices: dict[datetime, float]) -> bool:
    return len(prices) >= periods.month_days(year, month) * 23
