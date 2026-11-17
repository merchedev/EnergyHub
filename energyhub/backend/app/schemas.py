from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ContractIn(BaseModel):
    name: str = Field(default="Mi contrato", max_length=120)
    provider: str = Field(default="Pepe Energy", max_length=80)
    country: str = Field(default="ES", min_length=2, max_length=2)
    region: str | None = Field(default=None, max_length=8)
    timezone: str = Field(default="Europe/Madrid", max_length=64)
    tariff_type: str = Field(default="pepe_variable", max_length=40)
    tariff_profile_id: str = Field(default="pepe_variable", max_length=60)
    access_toll: str = Field(default="2.0TD", max_length=20)
    segment: str | None = Field(default="1", max_length=20)
    power_p1_kw: float = Field(default=4.6, ge=0, le=100)
    power_p2_kw: float = Field(default=4.6, ge=0, le=100)
    service_fee_eur_month: float = Field(default=3.996196, ge=0)
    social_bond_eur_month: float = Field(default=0.908639, ge=0)
    meter_rent_eur_month: float = Field(default=0.81, ge=0)
    other_fees_eur_month: float = Field(default=0.0, ge=0)
    vat_rate: float = Field(default=0.21, ge=0, le=1)
    electricity_tax_rate: float = Field(default=0.0511269632, ge=0, le=1)
    has_pepephone_discount: bool = False
    bono_social_category: str = Field(default="none", pattern=r"^(none|vulnerable|severe|exclusion)$")
    bono_social_energy_limit_kwh: float = Field(default=1587.0, ge=0)
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    billing_day: int = Field(default=1, ge=1, le=28)
    notes: str | None = None


class ContractOut(ContractIn):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class TariffPriceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    contract_id: int
    valid_from: date
    valid_to: date | None
    month_label: str
    source: str
    status: str
    p1_price: float
    p2_price: float
    p3_price: float
    power_p1_price: float
    power_p2_price: float
    service_fee_eur_month: float | None
    social_bond_eur_month: float | None
    vat_rate: float | None
    electricity_tax_rate: float | None
    fetched_at: datetime
    notes: str | None


class PriceProposalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    contract_id: int
    month_label: str
    valid_from: date
    p1_price: float
    p2_price: float
    p3_price: float
    power_p1_price: float
    power_p2_price: float
    service_fee_eur_month: float | None
    social_bond_eur_month: float | None
    vat_rate: float | None
    electricity_tax_rate: float | None
    source: str
    status: str
    fetched_at: datetime
    error: str | None


class ManualPriceIn(BaseModel):
    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    p1_price: float = Field(ge=0, le=5)
    p2_price: float = Field(ge=0, le=5)
    p3_price: float = Field(ge=0, le=5)
    power_p1_price: float = Field(default=0.0, ge=0, le=5)
    power_p2_price: float = Field(default=0.0, ge=0, le=5)
    service_fee_eur_month: float | None = Field(default=None, ge=0)
    social_bond_eur_month: float | None = Field(default=None, ge=0)
    vat_rate: float | None = Field(default=None, ge=0, le=1)
    electricity_tax_rate: float | None = Field(default=None, ge=0, le=1)
    source: str = Field(default="manual", max_length=40)
    notes: str | None = None


class WindowIn(BaseModel):
    start: str = Field(pattern=r"^\d{2}:\d{2}$")
    end: str = Field(pattern=r"^\d{2}:\d{2}$")
    weight: float = Field(default=1.0, gt=0, le=10)


class DeviceIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    category: str = Field(default="other", max_length=40)
    icon: str | None = Field(default=None, max_length=40)
    area: str | None = Field(default=None, max_length=80)
    mode: str = Field(default="always_on", pattern=r"^(always_on|hours_per_day|cycles|entity)$")
    power_active_w: float = Field(default=100.0, ge=0, le=100000)
    power_standby_w: float = Field(default=0.0, ge=0, le=10000)
    duty_cycle_pct: float = Field(default=100.0, ge=0, le=100)
    annual_kwh: float | None = Field(default=None, ge=0, le=100000)
    hours_per_day: float = Field(default=0.0, ge=0, le=24)
    cycles_per_week: float = Field(default=0.0, ge=0, le=100)
    minutes_per_cycle: float = Field(default=0.0, ge=0, le=1440)
    energy_per_cycle_kwh: float | None = Field(default=None, ge=0, le=1000)
    always_plugged: bool = True
    typical_windows: list[WindowIn] | None = None
    flexibility: str = Field(default="none", pattern=r"^(flexible|semi|none)$")
    entity_id: str | None = Field(default=None, max_length=160)
    energy_entity_id: str | None = Field(default=None, max_length=160)
    enabled: bool = True
    notes: str | None = None

    @field_validator("typical_windows")
    @classmethod
    def _validate_windows(cls, value: list[WindowIn] | None) -> list[WindowIn] | None:
        if value is not None and len(value) > 8:
            raise ValueError("Máximo 8 franjas por dispositivo")
        return value


class DeviceOut(DeviceIn):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_demo: bool
    created_at: datetime
    updated_at: datetime


class DevicePreviewIn(BaseModel):
    device: DeviceIn
    month: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")


class PeriodEstimateOut(BaseModel):
    id: str
    name: str
    price: float
    energy_kwh: float
    cost_eur: float


class DevicePreviewOut(BaseModel):
    energy_kwh: float
    active_kwh: float
    standby_kwh: float
    cost_eur: float
    min_cost_eur: float
    max_cost_eur: float
    confidence: str
    periods: list[PeriodEstimateOut]
    typical_windows: list[WindowIn] = []
    notes: list[str] = []
    price_available: bool = False
    price_is_fallback: bool = False
    price_month: str | None = None
    price_month_label: str | None = None
    price_source: str | None = None
    currency: str = "EUR"
    energy_source: str = "estimated"
    energy_resolution: str = "estimated"
    energy_entity_id: str | None = None
    energy_error: str | None = None


class CalibrationIn(BaseModel):
    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    actual_kwh: float = Field(gt=0, le=100000)
    actual_cost_eur: float | None = Field(default=None, ge=0, le=100000)
    notes: str | None = None


class CalibrationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    contract_id: int
    period_start: date
    period_end: date
    actual_kwh: float
    actual_cost_eur: float | None
    estimated_kwh: float
    estimated_cost_eur: float
    factor: float
    notes: str | None
    created_at: datetime


class SettingsUpdate(BaseModel):
    esios_entity_id: str | None = Field(default=None, max_length=160)
    language: str | None = Field(default=None, max_length=8)
    theme: str | None = Field(default=None, max_length=16)
    shift_flexible_pct: float | None = Field(default=None, ge=0, le=100)
    shift_semi_pct: float | None = Field(default=None, ge=0, le=100)


class ComparatorOut(BaseModel):
    month: str
    current_total: float
    alternative_total: float
    savings_eur_month: float
    current_label: str
    alternative_label: str
    current_energy_cost: float
    alternative_energy_cost: float
    pvpc_available: bool
    missing_hours: int
    pvpc_coverage: float
    notes: list[str] = []


class RecommendationOut(BaseModel):
    id: str
    rule: str
    device_id: int | None
    device_name: str | None = None
    severity: str
    title: str
    description: str
    savings_eur_month: float
    confidence: str
    action: str
    automation_kind: str | None = None
    yaml: str | None = None
    copy_yaml: str | None = None
    can_create_automation: bool = False
    status: str = "active"


class HaEntityOut(BaseModel):
    entity_id: str
    name: str
    domain: str
    state: str
    unit: str | None = None
    device_class: str | None = None
    state_class: str | None = None


class HaStatusOut(BaseModel):
    configured: bool
    connected: bool
    version: str | None = None
    location_name: str | None = None
    timezone: str | None = None
    error: str | None = None
