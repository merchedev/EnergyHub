export type PeriodId = 'P1' | 'P2' | 'P3'
export type Confidence = 'alta' | 'media' | 'baja'
export type DeviceMode = 'always_on' | 'hours_per_day' | 'cycles' | 'entity'
export type Flexibility = 'flexible' | 'semi' | 'none'

export interface Window {
  start: string
  end: string
  weight: number
}

export interface Contract {
  id: number
  name: string
  provider: string
  country: string
  region: string | null
  timezone: string
  tariff_type: string
  access_toll: string
  segment: string | null
  power_p1_kw: number
  power_p2_kw: number
  service_fee_eur_month: number
  social_bond_eur_month: number
  meter_rent_eur_month: number
  other_fees_eur_month: number
  vat_rate: number
  electricity_tax_rate: number
  currency: string
  billing_day: number
  notes: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface PeriodPrice {
  id: PeriodId
  name: string
  price: number
}

export interface PriceInfo {
  id: number
  month_label: string
  valid_from: string
  valid_to: string | null
  source: string
  status: string
  is_fallback: boolean
  p1_price: number
  p2_price: number
  p3_price: number
  power_p1_price: number
  power_p2_price: number
  service_fee_eur_month: number | null
  social_bond_eur_month: number | null
  vat_rate: number | null
  electricity_tax_rate: number | null
  periods: PeriodPrice[]
  reference_month: string
  requested_month: string
}

export interface FixedBreakdown {
  days: number
  energy_kwh: number
  energy_cost: number
  power_cost: number
  service_fee: number
  social_bond: number
  meter_rent: number
  other_fees: number
  fees_total: number
  electricity_tax: number
  vat: number
  taxable_base: number
  total: number
  energy_prices: Record<PeriodId, number>
  electricity_tax_rate: number
  vat_rate: number
}

export interface PriceProposal {
  id: number
  contract_id: number
  month_label: string
  valid_from: string
  p1_price: number
  p2_price: number
  p3_price: number
  power_p1_price: number
  power_p2_price: number
  service_fee_eur_month: number | null
  social_bond_eur_month: number | null
  vat_rate: number | null
  electricity_tax_rate: number | null
  source: string
  status: string
  fetched_at: string
  error: string | null
}

export interface CatalogItem {
  id: string
  name: string
  icon: string
  description: string
  mode: DeviceMode
  power_active_w: number
  power_standby_w: number
  duty_cycle_pct: number
  annual_kwh: number | null
  hours_per_day: number
  cycles_per_week: number
  minutes_per_cycle: number
  energy_per_cycle_kwh: number | null
  always_plugged: boolean
  typical_windows: Window[]
  flexibility: Flexibility
}

export interface Device {
  id: number
  name: string
  category: string
  icon: string | null
  area: string | null
  mode: DeviceMode
  power_active_w: number
  power_standby_w: number
  duty_cycle_pct: number
  annual_kwh: number | null
  hours_per_day: number
  cycles_per_week: number
  minutes_per_cycle: number
  energy_per_cycle_kwh: number | null
  always_plugged: boolean
  typical_windows: Window[]
  flexibility: Flexibility
  entity_id: string | null
  enabled: boolean
  notes: string | null
  is_demo: boolean
  energy_kwh: number
  active_kwh: number
  standby_kwh: number
  cost: number
  min_cost: number
  max_cost: number
  share: number
  confidence: Confidence
  by_period: Record<PeriodId, number>
  cost_by_period: Record<PeriodId, number>
  periods: Array<{ id: PeriodId; name: string; price: number; energy_kwh: number; cost_eur: number }>
  notes_estimate: string[]
}

export interface DeviceInput {
  name: string
  category: string
  icon?: string | null
  area?: string | null
  mode: DeviceMode
  power_active_w: number
  power_standby_w: number
  duty_cycle_pct: number
  annual_kwh?: number | null
  hours_per_day: number
  cycles_per_week: number
  minutes_per_cycle: number
  energy_per_cycle_kwh?: number | null
  always_plugged: boolean
  typical_windows?: Window[] | null
  flexibility: Flexibility
  entity_id?: string | null
  enabled: boolean
  notes?: string | null
}

export interface DevicePreview {
  energy_kwh: number
  active_kwh: number
  standby_kwh: number
  cost_eur: number
  min_cost_eur: number
  max_cost_eur: number
  confidence: Confidence
  periods: Array<{ id: PeriodId; name: string; price: number; energy_kwh: number; cost_eur: number }>
  typical_windows: Window[]
  notes: string[]
}

export interface DeviceSummary {
  energy_kwh: number
  cost: number
  count: number
  calibration_factor: number
  price: PriceInfo | null
}

export interface Totals {
  energy_kwh: number
  energy_cost: number
  power_cost: number
  fees_total: number
  electricity_tax: number
  vat: number
  total: number
  fixed_total: number
  variable_cost: number
  calibration_factor: number
  confidence: Confidence
  confidence_score: number
}

export interface DataQuality {
  score: number
  label: Confidence
  calibrated: boolean
  devices: number
  calibration_factor: number
}

export interface Dashboard {
  month: string
  month_label: string
  contract: Contract
  price: PriceInfo | null
  totals: Totals
  by_period: Array<{ id: PeriodId; name: string; energy_kwh: number; cost: number; price: number }>
  devices: Device[]
  top_devices: Device[]
  next_cheap_windows: CheapWindow[]
  recommendations_count: number
  esios: {
    configured: boolean
    entity_id: string | null
    connected: boolean
    price: number | null
    state: string | null
    unit: string | null
  }
  data_quality: DataQuality
  setup: {
    needs_price: boolean
    needs_devices: boolean
    needs_calibration: boolean
  }
}

export interface CheapWindow {
  start: string
  end: string
  label: string
  hours: number
  period: PeriodId
}

export interface CalendarDay {
  date: string
  weekday: string
  day: number
  month: string
  is_holiday: boolean
  is_today: boolean
  windows: Array<{
    id: PeriodId
    name: string
    start: string
    end: string
    price: number
  }>
}

export interface CalendarResponse {
  month: string
  price: PriceInfo | null
  periods: PeriodPrice[]
  days: CalendarDay[]
  cheap_windows: CheapWindow[]
}

export interface Recommendation {
  id: string
  rule: string
  device_id: number | null
  device_name: string | null
  severity: 'high' | 'medium' | 'info' | 'warning'
  title: string
  description: string
  savings_eur_month: number
  confidence: Confidence
  action: string
  automation_kind: 'reminder' | 'turn_off' | null
  yaml: string | null
  copy_yaml: string | null
  can_create_automation: boolean
  status: string
}

export interface ChangelogEntry {
  version: string
  date: string | null
  notes: string[]
}

export interface ChangelogResponse {
  installed_version: string
  latest_version: string
  entries: ChangelogEntry[]
  update_available: boolean
  source: 'supervisor' | 'github' | 'local'
  checked: boolean
  full_changelog_url: string
  error: string | null
  fetched_at: string | null
}

export interface HaEntity {
  entity_id: string
  name: string
  domain: string
  state: string
  unit: string | null
  device_class: string | null
}

export interface HaStatus {
  configured: boolean
  connected: boolean
  version: string | null
  location_name: string | null
  timezone: string | null
  error: string | null
}

export interface Bootstrap {
  has_contract: boolean
  has_devices: boolean
  has_price: boolean
  device_count: number
  demo_mode: boolean
  ha: HaStatus
  app_version: string
}

export interface Calibration {
  id: number
  contract_id: number
  period_start: string
  period_end: string
  actual_kwh: number
  actual_cost_eur: number | null
  estimated_kwh: number
  estimated_cost_eur: number
  factor: number
  notes: string | null
  created_at: string
}
