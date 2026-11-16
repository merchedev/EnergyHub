from __future__ import annotations

import threading
from collections.abc import Iterable
from dataclasses import dataclass
from functools import wraps

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import Calibration, Contract, Device, Recommendation, TariffPrice
from .estimation import DeviceEstimate

CATEGORY_TIPS = {
    "fridge": "Revisa la temperatura (4 °C nevera / -18 °C congelador), las gomas y la ventilación trasera.",
    "freezer": "Evita abrirlo muchas veces y revisa que no se forme hielo.",
    "washing_machine": "Usa programas eco, cargas completas y agua fría cuando puedas.",
    "dryer": "Cada ciclo gasta mucho; tiende al aire cuando sea posible.",
    "dishwasher": "Aprovecha cargas completas y el programa eco.",
    "oven": "Aprovecha el calor residual y evita precalentar si no hace falta.",
    "vitro": "Usa el diámetro adecuado, tapa las cazuelas y aprovecha el calor residual.",
    "microwave": "Es más eficiente que el horno para porciones pequeñas.",
    "tv": "Baja el brillo y evita el standby prolongado.",
    "computer": "Suspende el equipo y usa regletas con interruptor.",
    "console": "Activa el apagado automático y evita dejarla en reposo.",
    "water_heater": "Baja la temperatura y programa el calentamiento en valle.",
    "ac": "Cada grado de más encarece la factura; usa 25–26 °C en verano y mantenimiento limpio.",
    "heater": "Baja el termostato y mejora el aislamiento; es uno de los consumos más caros.",
    "lighting": "Sustituye halógenos por LED y usa sensores en zonas de paso.",
    "router": "Es un consumo pequeño pero constante; no hace falta apagarlo.",
    "ev": "Programa la carga en valle; es la carga flexible más importante.",
}


@dataclass
class RecDraft:
    id: str
    rule: str
    device_id: int | None
    severity: str
    title: str
    description: str
    savings_eur_month: float
    confidence: str
    action: str
    automation_kind: str | None = None


def _automation_id(title: str) -> str:
    import re
    import uuid

    slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")[:48] or "automatizacion"
    return f"energyhub_{slug}_{uuid.uuid4().hex[:6]}"


def _safe_yaml(data: dict) -> str:
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False).strip()


def build_automation_yaml(
    kind: str,
    device: Device,
    title: str,
) -> str:
    if kind == "reminder":
        payload = {
            "alias": f"EnergyHub · {title}",
            "description": "Creado por EnergyHub. Te avisa cuando empieza el tramo valle. Revisa el horario antes de usarlo.",
            "mode": "single",
            "trigger": [{"platform": "time", "at": "00:05:00"}],
            "condition": [],
            "action": [
                {
                    "service": "persistent_notification.create",
                    "data": {
                        "title": "EnergyHub · Hora valle",
                        "message": f"Es un buen momento para usar {device.name}. Estás en tramo valle.",
                    },
                }
            ],
        }
    elif kind == "turn_off":
        payload = {
            "alias": f"EnergyHub · Apagar {device.name}",
            "description": "Creado por EnergyHub. Apaga el dispositivo al empezar el tramo valle. Revisa que sea seguro.",
            "mode": "single",
            "trigger": [{"platform": "time", "at": "00:00:00"}],
            "condition": [],
            "action": [
                {
                    "service": "homeassistant.turn_off",
                    "target": {"entity_id": device.entity_id},
                }
            ],
        }
    else:
        return ""
    return _safe_yaml(payload)


def build_copy_yaml(device: Device) -> str:
    if not device.entity_id:
        return ""
    payload = {
        "alias": f"EnergyHub · {device.name} en valle",
        "description": "Creado por EnergyHub. Revisa que encender el aparato a esta hora sea seguro.",
        "mode": "single",
        "trigger": [{"platform": "time", "at": "00:05:00"}],
        "condition": [],
        "action": [
            {
                "service": "homeassistant.turn_on",
                "target": {"entity_id": device.entity_id},
            }
        ],
    }
    return _safe_yaml(payload)


def _upsert(db: Session, draft: RecDraft) -> Recommendation:
    existing = db.get(Recommendation, draft.id)
    if existing is None:
        existing = Recommendation(id=draft.id)
        db.add(existing)
    existing.rule = draft.rule
    existing.device_id = draft.device_id
    existing.severity = draft.severity
    existing.title = draft.title
    existing.description = draft.description
    existing.savings_eur_month = draft.savings_eur_month
    existing.confidence = draft.confidence
    existing.action = draft.action
    existing.automation_kind = draft.automation_kind
    if existing.status not in {"dismissed", "done"}:
        existing.status = "active"
    return existing


_RECOMMENDATION_LOCK = threading.Lock()


def _serialized(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        with _RECOMMENDATION_LOCK:
            return func(*args, **kwargs)

    return wrapper


@_serialized
def generate_recommendations(
    db: Session,
    contract: Contract,
    price: TariffPrice | None,
    price_is_fallback: bool,
    year: int,
    month: int,
    device_rows: Iterable[tuple[Device, DeviceEstimate]],
    calibration: Calibration | None,
    ha_configured: bool = False,
) -> list[Recommendation]:
    rows = list(device_rows)
    total_cost = sum(est.cost_eur for _device, est in rows) or 0.0
    total_kwh = sum(est.energy_kwh for _device, est in rows) or 0.0
    drafts: list[RecDraft] = []

    sorted_rows = sorted(rows, key=lambda row: row[1].cost_eur, reverse=True)
    for device, est in sorted_rows[:3]:
        share = (est.cost_eur / total_cost * 100.0) if total_cost > 0 else 0.0
        if share < 15.0 and len(drafts) >= 2:
            continue
        if est.cost_eur <= 0.5:
            continue
        tip = CATEGORY_TIPS.get(device.category, "Revisa si realmente necesitas ese consumo y si puedes reducirlo.")
        drafts.append(
            RecDraft(
                id=f"rec-top-{device.id}",
                rule="top_consumer",
                device_id=device.id,
                severity="high" if share >= 20 else "info",
                title=f"{device.name} concentra el {share:.0f}% del gasto",
                description=(
                    f"Consume unos {est.energy_kwh:.1f} kWh y cuesta {est.cost_eur:.2f} € al mes. "
                    f"{tip}"
                ),
                savings_eur_month=0.0,
                confidence=est.confidence,
                action=tip,
            )
        )

    if price is not None:
        p1, p2, p3 = price.p1_price, price.p2_price, price.p3_price
        average_price = (p1 + p2 + p3) / 3.0

        # Cargas que se pueden desplazar a valle.
        for device, est in rows:
            if device.flexibility == "none" or device.mode == "always_on":
                continue
            energy_shiftable = est.by_period.get("P1", 0.0) + est.by_period.get("P2", 0.0)
            if energy_shiftable <= 0.1:
                continue
            shift = 0.7 if device.flexibility == "flexible" else 0.3
            savings = (
                est.by_period.get("P1", 0.0) * max(0.0, p1 - p3) * shift
                + est.by_period.get("P2", 0.0) * max(0.0, p2 - p3) * shift
            )
            if savings < 0.3:
                continue
            drafts.append(
                RecDraft(
                    id=f"rec-shift-{device.id}",
                    rule="shift_to_valle",
                    device_id=device.id,
                    severity="high" if savings >= 3 else "medium",
                    title=f"Mueve {device.name} a valle",
                    description=(
                        f"Estimas {energy_shiftable:.1f} kWh en punta/llano. Pasando el "
                        f"{shift * 100:.0f}% a valle ahorrarías unos {savings:.2f} €/mes."
                    ),
                    savings_eur_month=round(savings, 2),
                    confidence=est.confidence,
                    action="Programa el aparato al empezar el tramo valle o usa una automatización.",
                    automation_kind="reminder",
                )
            )

        # Standby en cualquier aparato, también los no flexibles.
        for device, est in rows:
            if device.power_standby_w <= 0 or not device.always_plugged:
                continue
            if est.standby_kwh < 0.2:
                continue
            standby_cost = est.standby_kwh * average_price
            if standby_cost < 0.15:
                continue
            drafts.append(
                RecDraft(
                    id=f"rec-standby-{device.id}",
                    rule="standby",
                    device_id=device.id,
                    severity="medium",
                    title=f"El standby de {device.name} cuesta {standby_cost:.2f} €/mes",
                    description=(
                        f"Dejar {device.name} enchufado cuando no se usa supone unos "
                        f"{est.standby_kwh:.1f} kWh al mes. Una regleta o enchufe inteligente "
                        "puede eliminarlo."
                    ),
                    savings_eur_month=round(standby_cost, 2),
                    confidence=est.confidence,
                    action="Apaga el aparato o usa un enchufe con interruptor.",
                    automation_kind="turn_off" if device.entity_id else "reminder",
                )
            )

        # Aparatos que funcionan 24 h y pesan mucho en la factura.
        for device, est in rows:
            if device.mode != "always_on" or not device.always_plugged:
                continue
            share = (est.cost_eur / total_cost * 100.0) if total_cost > 0 else 0.0
            if share < 20 or est.energy_kwh < 20:
                continue
            tip = CATEGORY_TIPS.get(
                device.category, "Revisa si puede funcionar menos tiempo o con menor potencia."
            )
            drafts.append(
                RecDraft(
                    id=f"rec-always-{device.id}",
                    rule="always_on",
                    device_id=device.id,
                    severity="info",
                    title=f"{device.name} está encendido siempre",
                    description=(
                        f"Representa el {share:.0f}% del consumo estimado y {est.cost_eur:.2f} €/mes. "
                        f"{tip}"
                    ),
                    savings_eur_month=0.0,
                    confidence=est.confidence,
                    action=tip,
                )
            )

    if price_is_fallback and price is not None:
        drafts.append(
            RecDraft(
                id="rec-price-provisional",
                rule="price_provisional",
                device_id=None,
                severity="warning",
                title="El precio de Pepe es provisional",
                description=(
                    f"Estás usando los precios de {price.month_label} para el mes actual. "
                    "Cuando Pepe publique el precio definitivo, confírmalo para ajustar la factura."
                ),
                savings_eur_month=0.0,
                confidence="alta",
                action="Revisa la tarifa y confirma el mes publicado.",
            )
        )

    if calibration is None:
        drafts.append(
            RecDraft(
                id="rec-calibrate",
                rule="calibration",
                device_id=None,
                severity="info",
                title="Calibra con tu última factura",
                description=(
                    "Todavía no has comparado la estimación con una factura real. Añade los kWh y el "
                    "importe para ajustar el modelo a tu casa."
                ),
                savings_eur_month=0.0,
                confidence="alta",
                action="Ve a Tarifa → Calibración e introduce tu última factura.",
            )
        )
    elif abs(calibration.factor - 1.0) >= 0.15:
        drafts.append(
            RecDraft(
                id="rec-calibration-deviation",
                rule="calibration",
                device_id=None,
                severity="warning",
                title="La estimación se desvía de tu factura",
                description=(
                    f"El factor de calibración es {calibration.factor:.2f}. Revisa las horas y potencias "
                    "de los aparatos que más pesan para afinar el cálculo."
                ),
                savings_eur_month=0.0,
                confidence="alta",
                action="Revisa los dispositivos con más consumo o vuelve a calibrar.",
            )
        )

    low_confidence = [device for device, est in rows if est.confidence == "baja"]
    if len(rows) >= 3 and total_kwh > 0 and low_confidence:
        drafts.append(
            RecDraft(
                id="rec-data-quality",
                rule="data_quality",
                device_id=None,
                severity="info",
                title="Mejora la precisión de la estimación",
                description=(
                    f"Hay {len(low_confidence)} dispositivos con confianza baja. Añadir una entidad "
                    "de encendido/apagado o una franja de uso mejora el cálculo."
                ),
                savings_eur_month=0.0,
                confidence="alta",
                action="Revisa los dispositivos marcados con confianza baja.",
            )
        )

    if not rows:
        drafts.append(
            RecDraft(
                id="rec-add-devices",
                rule="add_devices",
                device_id=None,
                severity="info",
                title="Añade tus primeros aparatos",
                description="Para estimar la factura necesitamos saber qué hay enchufado y cuánto consume.",
                savings_eur_month=0.0,
                confidence="alta",
                action="Añade la nevera, la lavadora, la vitro y los aparatos que más uses.",
            )
        )

    current_ids = {draft.id for draft in drafts}
    # Usamos una sesión propia para que la generación sea idempotente y no
    # dependa de la instantánea de la sesión que pintó el dashboard.
    with SessionLocal() as rec_db:
        existing = rec_db.scalars(select(Recommendation)).all()
        for rec in existing:
            if rec.id not in current_ids and rec.status == "active":
                rec.status = "stale"
        for draft in drafts:
            _upsert(rec_db, draft)
        rec_db.commit()
        active = rec_db.scalars(
            select(Recommendation)
            .where(Recommendation.status == "active")
            .order_by(Recommendation.savings_eur_month.desc(), Recommendation.id)
        ).all()
        result = list(active)
    return result


def recommendation_payload(
    rec: Recommendation,
    device: Device | None,
    ha_configured: bool,
) -> dict:
    yaml_text = ""
    copy_yaml = ""
    can_create = False
    if device is not None and rec.automation_kind:
        yaml_text = build_automation_yaml(rec.automation_kind, device, rec.title)
        copy_yaml = build_copy_yaml(device) if rec.automation_kind == "reminder" else ""
        if ha_configured:
            if rec.automation_kind == "reminder":
                can_create = True
            elif rec.automation_kind == "turn_off" and device.entity_id:
                can_create = True
    return {
        "id": rec.id,
        "rule": rec.rule,
        "device_id": rec.device_id,
        "device_name": device.name if device else None,
        "severity": rec.severity,
        "title": rec.title,
        "description": rec.description,
        "savings_eur_month": rec.savings_eur_month,
        "confidence": rec.confidence,
        "action": rec.action,
        "automation_kind": rec.automation_kind,
        "yaml": yaml_text or None,
        "copy_yaml": copy_yaml or None,
        "can_create_automation": can_create,
        "status": rec.status,
    }


def mark_dismissed(db: Session, rec: Recommendation) -> None:
    rec.status = "dismissed"
    db.commit()


def has_active_recommendations(db: Session) -> int:
    return len(db.scalars(select(Recommendation).where(Recommendation.status == "active")).all())
