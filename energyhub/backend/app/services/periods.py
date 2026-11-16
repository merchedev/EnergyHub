from __future__ import annotations

import calendar
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import holidays as holidays_lib

PERIOD_NAMES = {"P1": "Punta", "P2": "Llano", "P3": "Valle"}
PERIOD_ORDER = ("P1", "P2", "P3")
SPANISH_MONTHS = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}
WEEKDAYS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MONTHS_ES = [
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
]

_HOLIDAY_CACHE: dict[tuple[str, str | None, int], set[date]] = {}


def _holidays_for_year(country: str, region: str | None, year: int) -> set[date]:
    key = (country.upper(), region or None, year)
    if key in _HOLIDAY_CACHE:
        return _HOLIDAY_CACHE[key]
    found: set[date] = set()
    try:
        if region:
            calendar_obj = holidays_lib.country_holidays(country.upper(), subdiv=region, years=[year])
        else:
            calendar_obj = holidays_lib.country_holidays(country.upper(), years=[year])
        found = set(calendar_obj.keys())
    except Exception:
        try:
            found = set(holidays_lib.country_holidays(country.upper(), years=[year]).keys())
        except Exception:
            found = set()
    _HOLIDAY_CACHE[key] = found
    return found


def is_holiday(day: date, country: str = "ES", region: str | None = None) -> bool:
    return day in _holidays_for_year(country, region, day.year)


def period_for_datetime(
    dt: datetime,
    country: str = "ES",
    region: str | None = None,
    tz: ZoneInfo | None = None,
) -> str:
    if tz is not None:
        dt = dt.astimezone(tz)
    if dt.weekday() >= 5 or is_holiday(dt.date(), country, region):
        return "P3"
    hour = dt.hour
    if 10 <= hour < 14 or 18 <= hour < 22:
        return "P1"
    if 8 <= hour < 10 or 14 <= hour < 18 or 22 <= hour < 24:
        return "P2"
    return "P3"


def period_for_time(
    day: date,
    hour: int,
    country: str = "ES",
    region: str | None = None,
    tz: ZoneInfo | None = None,
) -> str:
    dt = datetime.combine(day, time(hour=hour), tzinfo=tz or ZoneInfo("Europe/Madrid"))
    return period_for_datetime(dt, country=country, region=region)


def _full_day() -> list[dict]:
    return [{"id": "P3", "name": PERIOD_NAMES["P3"], "start": "00:00", "end": "24:00"}]


def day_windows(day: date, country: str = "ES", region: str | None = None) -> list[dict]:
    if day.weekday() >= 5 or is_holiday(day, country, region):
        return _full_day()
    return [
        {"id": "P3", "name": PERIOD_NAMES["P3"], "start": "00:00", "end": "08:00"},
        {"id": "P2", "name": PERIOD_NAMES["P2"], "start": "08:00", "end": "10:00"},
        {"id": "P1", "name": PERIOD_NAMES["P1"], "start": "10:00", "end": "14:00"},
        {"id": "P2", "name": PERIOD_NAMES["P2"], "start": "14:00", "end": "18:00"},
        {"id": "P1", "name": PERIOD_NAMES["P1"], "start": "18:00", "end": "22:00"},
        {"id": "P2", "name": PERIOD_NAMES["P2"], "start": "22:00", "end": "24:00"},
    ]


def p3_windows(day: date, country: str = "ES", region: str | None = None) -> list[tuple[int, int]]:
    """Return valle windows as minutes from midnight."""
    if day.weekday() >= 5 or is_holiday(day, country, region):
        return [(0, 24 * 60)]
    return [(0, 8 * 60)]


def month_days(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def month_bounds(year: int, month: int) -> tuple[date, date]:
    first = date(year, month, 1)
    last = date(year, month, month_days(year, month))
    return first, last


def month_label_es(year: int, month: int) -> str:
    return f"{MONTHS_ES[month - 1]} de {year}"


def month_label_short(year: int, month: int) -> str:
    return f"{MONTHS_ES[month - 1].capitalize()} {year}"


def parse_month(value: str | None, tz: ZoneInfo | None = None) -> tuple[int, int]:
    if value:
        try:
            y, m = value.split("-")
            y_int, m_int = int(y), int(m)
            if 1 <= m_int <= 12:
                return y_int, m_int
        except Exception:
            pass
    now = datetime.now(tz or ZoneInfo("Europe/Madrid"))
    return now.year, now.month


def parse_spanish_month(label: str | None, fallback: date | None = None) -> date:
    if label:
        parts = label.strip().lower().replace(",", "").split()
        if len(parts) >= 2:
            month = SPANISH_MONTHS.get(parts[0])
            try:
                year = int(parts[1])
            except ValueError:
                year = None
            if month and year:
                return date(year, month, 1)
    if fallback is not None:
        return date(fallback.year, fallback.month, 1)
    today = datetime.now(timezone.utc).date()
    first = today.replace(day=1)
    previous = first - timedelta(days=1)
    return previous.replace(day=1)


def month_period_hours(
    year: int,
    month: int,
    tz: ZoneInfo,
    country: str = "ES",
    region: str | None = None,
) -> dict[str, float]:
    """Count real local hours per tariff period, including DST transitions."""
    first_local = datetime(year, month, 1, tzinfo=tz)
    if month == 12:
        next_local = datetime(year + 1, 1, 1, tzinfo=tz)
    else:
        next_local = datetime(year, month + 1, 1, tzinfo=tz)
    current = first_local.astimezone(timezone.utc)
    end = next_local.astimezone(timezone.utc)
    result = {p: 0.0 for p in PERIOD_ORDER}
    while current < end:
        local = current.astimezone(tz)
        result[period_for_datetime(local, country=country, region=region)] += 1.0
        current += timedelta(hours=1)
    return result


def _mins_from_hhmm(value: str) -> int:
    h, m = value.split(":")
    return int(h) * 60 + int(m)


def window_period_fractions(
    day: date,
    start: str,
    end: str,
    country: str = "ES",
    region: str | None = None,
    tz: ZoneInfo | None = None,
    step_minutes: int = 15,
) -> dict[str, float]:
    """Split a local window into period fractions (0..1), handling overnight windows."""
    tz = tz or ZoneInfo("Europe/Madrid")
    start_min = _mins_from_hhmm(start)
    end_min = _mins_from_hhmm(end)
    if end_min == 24 * 60:
        end_min = 24 * 60
    if end_min <= start_min:
        end_min += 24 * 60
    total = end_min - start_min
    if total <= 0:
        return {p: 0.0 for p in PERIOD_ORDER}
    counts = {p: 0.0 for p in PERIOD_ORDER}
    cursor = start_min
    while cursor < end_min:
        minutes = min(step_minutes, end_min - cursor)
        day_offset = cursor // (24 * 60)
        minute_of_day = cursor % (24 * 60)
        local_day = day + timedelta(days=day_offset)
        hour = minute_of_day // 60
        minute = minute_of_day % 60
        dt = datetime.combine(local_day, time(hour=hour, minute=minute), tzinfo=tz)
        period = period_for_datetime(dt, country=country, region=region)
        counts[period] += minutes
        cursor += minutes
    return {p: counts[p] / total for p in PERIOD_ORDER}


def window_hour_fractions(
    day: date,
    start: str,
    end: str,
    tz: ZoneInfo | None = None,
    step_minutes: int = 15,
) -> dict[datetime, float]:
    """Split a local window into fractions keyed by the local hour start."""
    tz = tz or ZoneInfo("Europe/Madrid")
    start_min = _mins_from_hhmm(start)
    end_min = _mins_from_hhmm(end)
    if end_min <= start_min:
        end_min += 24 * 60
    total = end_min - start_min
    if total <= 0:
        return {}
    counts: dict[datetime, float] = {}
    cursor = start_min
    while cursor < end_min:
        minutes = min(step_minutes, end_min - cursor)
        day_offset = cursor // (24 * 60)
        minute_of_day = cursor % (24 * 60)
        local_day = day + timedelta(days=day_offset)
        hour = minute_of_day // 60
        hour_dt = datetime.combine(local_day, time(hour=hour), tzinfo=tz)
        counts[hour_dt] = counts.get(hour_dt, 0.0) + minutes
        cursor += minutes
    return {hour: minutes / total for hour, minutes in counts.items()}


def next_cheap_windows(
    now: datetime,
    country: str = "ES",
    region: str | None = None,
    tz: ZoneInfo | None = None,
    count: int = 4,
    lookahead_days: int = 14,
) -> list[dict]:
    tz = tz or ZoneInfo("Europe/Madrid")
    now = now.astimezone(tz)
    today = now.date()
    result: list[dict] = []
    for offset in range(lookahead_days):
        day = today + timedelta(days=offset)
        for start_min, end_min in p3_windows(day, country, region):
            start_dt = datetime.combine(day, time(0, 0), tzinfo=tz) + timedelta(minutes=start_min)
            end_dt = datetime.combine(day, time(0, 0), tzinfo=tz) + timedelta(minutes=end_min)
            if end_dt <= now:
                continue
            if len(result) >= count:
                return result
            effective_start = max(start_dt, now)
            full_day = (end_min - start_min) >= 24 * 60
            in_window = start_dt <= now < end_dt
            if in_window:
                if full_day:
                    label = "Ahora, todo el día"
                else:
                    label = f"Ahora hasta las {end_dt.strftime('%H:%M')}"
            elif day == today:
                label = "Hoy, todo el día" if full_day else f"Hoy, {start_dt.strftime('%H:%M')}–{end_dt.strftime('%H:%M')}"
            elif day == today + timedelta(days=1):
                label = "Mañana, todo el día" if full_day else f"Mañana, {start_dt.strftime('%H:%M')}–{end_dt.strftime('%H:%M')}"
            else:
                weekday = WEEKDAYS_ES[day.weekday()].capitalize()
                label = (
                    f"{weekday} {day.day}, todo el día"
                    if full_day
                    else f"{weekday} {day.day}, {start_dt.strftime('%H:%M')}–{end_dt.strftime('%H:%M')}"
                )
            result.append(
                {
                    "start": start_dt.isoformat(),
                    "end": end_dt.isoformat(),
                    "label": label,
                    "hours": round((end_dt - effective_start).total_seconds() / 3600, 1),
                    "period": "P3",
                }
            )
    return result
