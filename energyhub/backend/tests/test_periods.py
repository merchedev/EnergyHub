from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.services import periods

TZ = ZoneInfo("Europe/Madrid")


def test_weekday_periods() -> None:
    day = date(2026, 11, 16)  # lunes
    assert periods.period_for_time(day, 2, tz=TZ) == "P3"
    assert periods.period_for_time(day, 9, tz=TZ) == "P2"
    assert periods.period_for_time(day, 12, tz=TZ) == "P1"
    assert periods.period_for_time(day, 15, tz=TZ) == "P2"
    assert periods.period_for_time(day, 20, tz=TZ) == "P1"
    assert periods.period_for_time(day, 23, tz=TZ) == "P2"


def test_weekend_is_all_valle() -> None:
    saturday = date(2026, 11, 21)
    windows = periods.day_windows(saturday)
    assert len(windows) == 1
    assert windows[0]["id"] == "P3"
    assert periods.period_for_time(saturday, 20, tz=TZ) == "P3"


def test_national_holiday_is_valle() -> None:
    christmas = date(2026, 12, 25)
    assert periods.is_holiday(christmas)
    assert periods.period_for_time(christmas, 20, tz=TZ) == "P3"


def test_month_hours_with_dst() -> None:
    november = periods.month_period_hours(2026, 11, TZ)
    assert sum(november.values()) == 720
    march = periods.month_period_hours(2026, 3, TZ)
    assert sum(march.values()) == 743  # cambio de hora de primavera


def test_window_period_fractions() -> None:
    day = date(2026, 11, 16)
    fractions = periods.window_period_fractions(day, "13:00", "15:00", tz=TZ)
    assert abs(fractions["P1"] - 0.5) < 0.001
    assert abs(fractions["P2"] - 0.5) < 0.001
    assert abs(fractions["P3"]) < 0.001

    weekend = periods.window_period_fractions(date(2026, 11, 21), "20:00", "22:00", tz=TZ)
    assert abs(weekend["P3"] - 1.0) < 0.001


def test_cheap_windows_are_spanish_and_include_full_weekend() -> None:
    now = datetime(2026, 11, 16, 13, 0, tzinfo=TZ)
    windows = periods.next_cheap_windows(now, tz=TZ, count=10)
    labels = [window["label"] for window in windows]
    assert any(label.startswith("Mañana") for label in labels)
    assert any("todo el día" in label for label in labels)
    assert any(label.startswith("Sábado") for label in labels)
    assert not any("Wednesday" in label for label in labels)
