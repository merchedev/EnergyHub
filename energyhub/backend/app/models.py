from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Contract(Base):
    __tablename__ = "contracts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), default="Mi contrato")
    provider: Mapped[str] = mapped_column(String(80), default="Pepe Energy")
    country: Mapped[str] = mapped_column(String(2), default="ES")
    region: Mapped[str | None] = mapped_column(String(8), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Madrid")
    tariff_type: Mapped[str] = mapped_column(String(40), default="pepe_variable")
    access_toll: Mapped[str] = mapped_column(String(20), default="2.0TD")
    segment: Mapped[str | None] = mapped_column(String(20), default="1")
    power_p1_kw: Mapped[float] = mapped_column(Float, default=4.6)
    power_p2_kw: Mapped[float] = mapped_column(Float, default=4.6)
    service_fee_eur_month: Mapped[float] = mapped_column(Float, default=3.996196)
    social_bond_eur_month: Mapped[float] = mapped_column(Float, default=0.908639)
    meter_rent_eur_month: Mapped[float] = mapped_column(Float, default=0.81)
    other_fees_eur_month: Mapped[float] = mapped_column(Float, default=0.0)
    vat_rate: Mapped[float] = mapped_column(Float, default=0.21)
    electricity_tax_rate: Mapped[float] = mapped_column(Float, default=0.0511269632)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    billing_day: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class TariffPrice(Base):
    __tablename__ = "tariff_prices"
    __table_args__ = (UniqueConstraint("contract_id", "valid_from", name="uq_tariff_price_month"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id", ondelete="CASCADE"), index=True)
    valid_from: Mapped[date] = mapped_column(Date, index=True)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    month_label: Mapped[str] = mapped_column(String(40), default="")
    source: Mapped[str] = mapped_column(String(40), default="manual")
    status: Mapped[str] = mapped_column(String(20), default="confirmed")
    p1_price: Mapped[float] = mapped_column(Float)
    p2_price: Mapped[float] = mapped_column(Float)
    p3_price: Mapped[float] = mapped_column(Float)
    power_p1_price: Mapped[float] = mapped_column(Float, default=0.0)
    power_p2_price: Mapped[float] = mapped_column(Float, default=0.0)
    service_fee_eur_month: Mapped[float | None] = mapped_column(Float, nullable=True)
    social_bond_eur_month: Mapped[float | None] = mapped_column(Float, nullable=True)
    vat_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    electricity_tax_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    raw_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PriceProposal(Base):
    __tablename__ = "price_proposals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id", ondelete="CASCADE"), index=True)
    month_label: Mapped[str] = mapped_column(String(40), default="")
    valid_from: Mapped[date] = mapped_column(Date)
    p1_price: Mapped[float] = mapped_column(Float)
    p2_price: Mapped[float] = mapped_column(Float)
    p3_price: Mapped[float] = mapped_column(Float)
    power_p1_price: Mapped[float] = mapped_column(Float, default=0.0)
    power_p2_price: Mapped[float] = mapped_column(Float, default=0.0)
    service_fee_eur_month: Mapped[float | None] = mapped_column(Float, nullable=True)
    social_bond_eur_month: Mapped[float | None] = mapped_column(Float, nullable=True)
    vat_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    electricity_tax_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(40), default="pepe_api")
    status: Mapped[str] = mapped_column(String(20), default="pending")
    raw_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(40), default="other")
    icon: Mapped[str | None] = mapped_column(String(40), nullable=True)
    area: Mapped[str | None] = mapped_column(String(80), nullable=True)
    mode: Mapped[str] = mapped_column(String(24), default="always_on")
    power_active_w: Mapped[float] = mapped_column(Float, default=100.0)
    power_standby_w: Mapped[float] = mapped_column(Float, default=0.0)
    duty_cycle_pct: Mapped[float] = mapped_column(Float, default=100.0)
    annual_kwh: Mapped[float | None] = mapped_column(Float, nullable=True)
    hours_per_day: Mapped[float] = mapped_column(Float, default=0.0)
    cycles_per_week: Mapped[float] = mapped_column(Float, default=0.0)
    minutes_per_cycle: Mapped[float] = mapped_column(Float, default=0.0)
    energy_per_cycle_kwh: Mapped[float | None] = mapped_column(Float, nullable=True)
    always_plugged: Mapped[bool] = mapped_column(Boolean, default=True)
    typical_windows_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    flexibility: Mapped[str] = mapped_column(String(20), default="none")
    entity_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Calibration(Base):
    __tablename__ = "calibrations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id", ondelete="CASCADE"), index=True)
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    actual_kwh: Mapped[float] = mapped_column(Float)
    actual_cost_eur: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_kwh: Mapped[float] = mapped_column(Float)
    estimated_cost_eur: Mapped[float] = mapped_column(Float, default=0.0)
    factor: Mapped[float] = mapped_column(Float, default=1.0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    rule: Mapped[str] = mapped_column(String(60))
    device_id: Mapped[int | None] = mapped_column(ForeignKey("devices.id", ondelete="SET NULL"), nullable=True)
    severity: Mapped[str] = mapped_column(String(20), default="info")
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    savings_eur_month: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[str] = mapped_column(String(20), default="media")
    action: Mapped[str] = mapped_column(Text, default="")
    automation_kind: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class AutomationLog(Base):
    __tablename__ = "automation_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recommendation_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ha_automation_id: Mapped[str] = mapped_column(String(120), unique=True)
    alias: Mapped[str] = mapped_column(String(200), default="")
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="created")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
