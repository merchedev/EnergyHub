from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from ..models import Contract, Device, TariffPrice
from .estimation import DeviceEstimate
from .tariff import effective_electricity_tax_rate, effective_vat_rate, period_prices

DEFAULT_SHIFT_FLEXIBLE_PCT = 70.0
DEFAULT_SHIFT_SEMI_PCT = 30.0


@dataclass
class CostComparison:
    actual_cost_eur: float
    all_p1_cost_eur: float
    all_p2_cost_eur: float
    all_p3_cost_eur: float
    savings_vs_p1_eur: float
    savings_vs_p2_eur: float
    max_saving_to_p3_eur: float
    actual_cost_with_taxes_eur: float
    all_p1_cost_with_taxes_eur: float
    all_p2_cost_with_taxes_eur: float
    all_p3_cost_with_taxes_eur: float
    savings_vs_p1_with_taxes_eur: float
    savings_vs_p2_with_taxes_eur: float
    max_saving_to_p3_with_taxes_eur: float
    energy_kwh: float
    by_period: dict[str, float] = field(default_factory=lambda: {"P1": 0.0, "P2": 0.0, "P3": 0.0})
    valle_share: float = 0.0
    savings_captured_pct: float = 0.0
    shiftable_energy_kwh: float = 0.0
    shiftable_saving_eur: float = 0.0
    shiftable_saving_with_taxes_eur: float = 0.0
    shift_factor: float = 0.0
    is_flexible: bool = False
    is_always_on: bool = False
    has_period_difference: bool = True
    price_mode: str = "period"
    price_is_fallback: bool = False
    note: str | None = None


def _clamp_pct(value: float) -> float:
    return max(0.0, min(100.0, float(value))) / 100.0


def _gross_multiplier(contract: Contract, price: TariffPrice) -> float:
    tax_rate = max(0.0, effective_electricity_tax_rate(contract, price))
    vat_rate = max(0.0, effective_vat_rate(contract, price))
    return (1.0 + tax_rate) * (1.0 + vat_rate)


def device_comparison(
    device: Device,
    est: DeviceEstimate,
    price: TariffPrice | None,
    contract: Contract,
    *,
    shift_flexible_pct: float = DEFAULT_SHIFT_FLEXIBLE_PCT,
    shift_semi_pct: float = DEFAULT_SHIFT_SEMI_PCT,
    price_is_fallback: bool = False,
) -> CostComparison | None:
    """Compare the actual cost with the same energy used in one single period."""
    energy = max(0.0, float(est.energy_kwh or 0.0))
    if price is None or energy <= 0:
        return None

    values = period_prices(price)
    p1 = max(0.0, float(values["P1"]))
    p2 = max(0.0, float(values["P2"]))
    p3 = max(0.0, float(values["P3"]))
    actual = max(0.0, float(est.cost_eur or 0.0))
    all_p1 = energy * p1
    all_p2 = energy * p2
    all_p3 = energy * p3
    gross = _gross_multiplier(contract, price)

    by_period = {
        "P1": max(0.0, float(est.by_period.get("P1", 0.0))),
        "P2": max(0.0, float(est.by_period.get("P2", 0.0))),
        "P3": max(0.0, float(est.by_period.get("P3", 0.0))),
    }
    valle_share = by_period["P3"] / energy * 100.0 if energy > 0 else 0.0
    valle_share = max(0.0, min(100.0, valle_share))

    gap = all_p1 - all_p3
    captured = ((all_p1 - actual) / gap * 100.0) if gap > 0.000001 else 0.0
    captured = max(0.0, min(100.0, captured))

    is_always_on = device.mode == "always_on"
    is_flexible = device.flexibility in {"flexible", "semi"} and not is_always_on
    if is_always_on or device.flexibility == "none":
        shift_factor = 0.0
    elif device.flexibility == "flexible":
        shift_factor = _clamp_pct(shift_flexible_pct)
    else:
        shift_factor = _clamp_pct(shift_semi_pct)

    shiftable_energy = by_period["P1"] + by_period["P2"] if is_flexible else 0.0
    shiftable_saving = shift_factor * (
        by_period["P1"] * max(0.0, p1 - p3) + by_period["P2"] * max(0.0, p2 - p3)
    )
    has_period_difference = not (
        abs(p1 - p2) < 1e-9 and abs(p2 - p3) < 1e-9
    )
    price_mode = "hourly" if price.source == "ree_pvpc" else "period"

    note: str | None = None
    if not has_period_difference:
        note = "Tu tarifa tiene el mismo precio en todos los tramos; el horario no cambia el coste."
    elif price_mode == "hourly":
        note = "Comparación aproximada con el precio medio de cada tramo PVPC."
    elif is_always_on:
        note = "Consumo continuo: la comparación es teórica y este aparato no se puede desplazar."
    elif not is_flexible:
        note = "No está marcado como flexible; no se calcula ahorro potencial."
    elif shiftable_saving <= 0.01 and valle_share >= 99.9:
        note = "Todo el consumo está en valle; no hay margen de mejora."
    elif shiftable_saving <= 0.01:
        note = "No hay margen de ahorro con la flexibilidad configurada."

    return CostComparison(
        actual_cost_eur=round(actual, 4),
        all_p1_cost_eur=round(all_p1, 4),
        all_p2_cost_eur=round(all_p2, 4),
        all_p3_cost_eur=round(all_p3, 4),
        savings_vs_p1_eur=round(all_p1 - actual, 4),
        savings_vs_p2_eur=round(all_p2 - actual, 4),
        max_saving_to_p3_eur=round(max(0.0, actual - all_p3), 4),
        actual_cost_with_taxes_eur=round(actual * gross, 4),
        all_p1_cost_with_taxes_eur=round(all_p1 * gross, 4),
        all_p2_cost_with_taxes_eur=round(all_p2 * gross, 4),
        all_p3_cost_with_taxes_eur=round(all_p3 * gross, 4),
        savings_vs_p1_with_taxes_eur=round((all_p1 - actual) * gross, 4),
        savings_vs_p2_with_taxes_eur=round((all_p2 - actual) * gross, 4),
        max_saving_to_p3_with_taxes_eur=round(max(0.0, actual - all_p3) * gross, 4),
        energy_kwh=round(energy, 4),
        by_period=by_period,
        valle_share=round(valle_share, 2),
        savings_captured_pct=round(captured, 1),
        shiftable_energy_kwh=round(shiftable_energy, 4),
        shiftable_saving_eur=round(shiftable_saving, 4),
        shiftable_saving_with_taxes_eur=round(shiftable_saving * gross, 4),
        shift_factor=round(shift_factor, 4),
        is_flexible=is_flexible,
        is_always_on=is_always_on,
        has_period_difference=has_period_difference,
        price_mode=price_mode,
        price_is_fallback=price_is_fallback,
        note=note,
    )


def aggregate_comparisons(comparisons: Iterable[CostComparison | None]) -> CostComparison | None:
    """Aggregate device comparisons into a household total."""
    items = [item for item in comparisons if item is not None]
    if not items:
        return None

    by_period = {"P1": 0.0, "P2": 0.0, "P3": 0.0}
    for item in items:
        for period in by_period:
            by_period[period] += item.by_period.get(period, 0.0)

    energy = sum(item.energy_kwh for item in items)
    actual = sum(item.actual_cost_eur for item in items)
    all_p1 = sum(item.all_p1_cost_eur for item in items)
    all_p2 = sum(item.all_p2_cost_eur for item in items)
    all_p3 = sum(item.all_p3_cost_eur for item in items)
    actual_tax = sum(item.actual_cost_with_taxes_eur for item in items)
    all_p1_tax = sum(item.all_p1_cost_with_taxes_eur for item in items)
    all_p2_tax = sum(item.all_p2_cost_with_taxes_eur for item in items)
    all_p3_tax = sum(item.all_p3_cost_with_taxes_eur for item in items)
    shiftable_saving = sum(item.shiftable_saving_eur for item in items)
    shiftable_saving_tax = sum(item.shiftable_saving_with_taxes_eur for item in items)
    gap = all_p1 - all_p3
    captured = ((all_p1 - actual) / gap * 100.0) if gap > 0.000001 else 0.0

    has_period_difference = any(item.has_period_difference for item in items)
    price_mode = items[0].price_mode
    price_is_fallback = any(item.price_is_fallback for item in items)
    note: str | None = None
    if not has_period_difference:
        note = "Tu tarifa tiene el mismo precio en todos los tramos; el horario no cambia el coste."
    elif price_mode == "hourly":
        note = "Comparación aproximada con el precio medio de cada tramo PVPC."
    elif price_is_fallback:
        note = "Con precios provisionales; se ajustará al confirmar la tarifa."

    return CostComparison(
        actual_cost_eur=round(actual, 4),
        all_p1_cost_eur=round(all_p1, 4),
        all_p2_cost_eur=round(all_p2, 4),
        all_p3_cost_eur=round(all_p3, 4),
        savings_vs_p1_eur=round(all_p1 - actual, 4),
        savings_vs_p2_eur=round(all_p2 - actual, 4),
        max_saving_to_p3_eur=round(max(0.0, actual - all_p3), 4),
        actual_cost_with_taxes_eur=round(actual_tax, 4),
        all_p1_cost_with_taxes_eur=round(all_p1_tax, 4),
        all_p2_cost_with_taxes_eur=round(all_p2_tax, 4),
        all_p3_cost_with_taxes_eur=round(all_p3_tax, 4),
        savings_vs_p1_with_taxes_eur=round(all_p1_tax - actual_tax, 4),
        savings_vs_p2_with_taxes_eur=round(all_p2_tax - actual_tax, 4),
        max_saving_to_p3_with_taxes_eur=round(max(0.0, actual_tax - all_p3_tax), 4),
        energy_kwh=round(energy, 4),
        by_period=by_period,
        valle_share=round((by_period["P3"] / energy * 100.0) if energy > 0 else 0.0, 2),
        savings_captured_pct=round(max(0.0, min(100.0, captured)), 1),
        shiftable_energy_kwh=round(sum(item.shiftable_energy_kwh for item in items), 4),
        shiftable_saving_eur=round(shiftable_saving, 4),
        shiftable_saving_with_taxes_eur=round(shiftable_saving_tax, 4),
        shift_factor=0.0,
        is_flexible=any(item.is_flexible for item in items),
        is_always_on=False,
        has_period_difference=has_period_difference,
        price_mode=price_mode,
        price_is_fallback=price_is_fallback,
        note=note,
    )
