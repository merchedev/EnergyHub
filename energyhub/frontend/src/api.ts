import type {
  Bootstrap,
  CalendarResponse,
  CatalogItem,
  ChangelogResponse,
  ComparatorResponse,
  Contract,
  Dashboard,
  Device,
  DeviceInput,
  DevicePreview,
  HaEntity,
  HaStatus,
  PriceCurve,
  PriceInfo,
  PriceProposal,
  Recommendation,
  Calibration,
  TariffProfile,
  TariffsResponse,
} from './types'

const API_BASE = import.meta.env.VITE_API_BASE ?? 'api'

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers ?? {}),
    },
  })
  if (!response.ok) {
    let message = `Error ${response.status}`
    try {
      const data = await response.json()
      if (typeof data?.detail === 'string') message = data.detail
      else if (Array.isArray(data?.detail)) message = data.detail.map((item: { msg?: string }) => item.msg).join('. ')
    } catch {
      // no-op
    }
    throw new ApiError(message, response.status)
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export const api = {
  bootstrap: () => request<Bootstrap>('/bootstrap'),
  catalog: () => request<{ items: CatalogItem[] }>('/catalog'),
  tariffs: () => request<TariffsResponse>('/tariffs'),
  changelog: () => request<ChangelogResponse>('/changelog'),
  contract: () => request<{ contract: Contract | null }>('/contract'),
  saveContract: (payload: Partial<Contract>) =>
    request<{ contract: Contract }>('/contract', { method: 'POST', body: JSON.stringify(payload) }),
  currentTariff: (month?: string) =>
    request<{
      contract: Contract
      profile: TariffProfile
      month: string
      month_label: string
      days: number
      price: PriceInfo | null
      periods: Array<{ id: string; name: string; price: number }>
      fixed: DashFixed | null
      price_mode: 'hourly' | 'period'
      calibration_factor: number
      calibration: Calibration | null
    }>(`/tariff/current${month ? `?month=${month}` : ''}`),
  calendar: (days = 7) => request<CalendarResponse>(`/tariff/calendar?days=${days}`),
  hourly: (days = 2, duration = 2) =>
    request<{
      profile: TariffProfile
      price_mode: 'hourly' | 'period'
      price: PriceInfo | null
      curve: PriceCurve
      cheap_windows: Array<{
        start: string
        end: string
        average_price: number
        hours: number
        period: string
        label: string
      }>
    }>(`/tariff/hourly?days=${days}&duration=${duration}`),
  comparator: (month?: string) =>
    request<ComparatorResponse>(`/comparator${month ? `?month=${month}` : ''}`),
  proposals: () => request<{ items: PriceProposal[] }>('/tariff/proposals'),
  fetchPepe: () =>
    request<{ proposal: PriceProposal; message: string }>('/tariff/pepe/fetch', { method: 'POST' }),
  confirmPepe: (proposalId: number) =>
    request<{ price: PriceInfo; current: PriceInfo | null }>('/tariff/pepe/confirm', {
      method: 'POST',
      body: JSON.stringify({ proposal_id: proposalId }),
    }),
  saveManualPrice: (payload: Record<string, unknown>) =>
    request<{ price: PriceInfo }>('/tariff/prices', { method: 'POST', body: JSON.stringify(payload) }),
  devices: () =>
    request<{
      items: Device[]
      summary: { energy_kwh: number; cost: number; count: number; calibration_factor: number; price: PriceInfo | null }
    }>('/devices'),
  previewDevice: (device: DeviceInput, month?: string) =>
    request<DevicePreview>('/devices/preview', {
      method: 'POST',
      body: JSON.stringify({ device, month }),
    }),
  createDevice: (device: DeviceInput) =>
    request<{ device: Device }>('/devices', { method: 'POST', body: JSON.stringify(device) }),
  updateDevice: (id: number, device: DeviceInput) =>
    request<{ device: Device }>(`/devices/${id}`, { method: 'PUT', body: JSON.stringify(device) }),
  deleteDevice: (id: number) => request<{ ok: boolean }>(`/devices/${id}`, { method: 'DELETE' }),
  dashboard: (month?: string) => request<Dashboard>(`/dashboard${month ? `?month=${month}` : ''}`),
  recommendations: () => request<{ items: Recommendation[] }>('/recommendations'),
  dismissRecommendation: (id: string) =>
    request<{ ok: boolean }>(`/recommendations/${id}/dismiss`, { method: 'POST' }),
  createAutomation: (id: string) =>
    request<{ ok: boolean; automation_id: string; alias: string }>(
      `/recommendations/${id}/create-automation`,
      { method: 'POST' },
    ),
  automations: () =>
    request<{ items: Array<{ id: number; automation_id: string; alias: string; created_at: string }> }>(
      '/automations',
    ),
  deleteAutomation: (automationId: string) =>
    request<{ ok: boolean }>(`/automations/${automationId}`, { method: 'DELETE' }),
  calibrate: (payload: { month: string; actual_kwh: number; actual_cost_eur?: number | null; notes?: string | null }) =>
    request<{ calibration: Calibration; factor: number; estimated_kwh: number; estimated_cost: number }>(
      '/calibrations',
      { method: 'POST', body: JSON.stringify(payload) },
    ),
  calibrations: () =>
    request<{ items: Calibration[]; factor: number }>('/calibrations'),
  haStatus: () => request<HaStatus>('/ha/status'),
  haEntities: (kind = 'all') => request<{ configured: boolean; items: HaEntity[] }>(`/ha/entities?kind=${kind}`),
  settings: () =>
    request<{ esios_entity_id: string; language: string; theme: string; demo_mode: boolean }>('/settings'),
  updateSettings: (payload: { esios_entity_id?: string | null; language?: string; theme?: string }) =>
    request<{ esios_entity_id: string; language: string; theme: string; demo_mode: boolean }>('/settings', {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  seedDemo: () => request<{ ok: boolean }>('/demo/seed', { method: 'POST' }),
  resetDemo: () => request<{ ok: boolean }>('/demo/reset', { method: 'POST' }),
  exportUrl: () => `${API_BASE}/export`,
}

export interface DashFixed {
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
  energy_prices: Record<string, number>
  electricity_tax_rate: number
  vat_rate: number
  energy_cost_original?: number
  power_cost_original?: number
  service_fee_original?: number
  service_discount?: number
  bono_social_discount?: number
  bono_social_percentage?: number
  bono_social_applied?: boolean
  bono_social_eligible?: boolean
  by_period?: Record<string, number>
  cost_by_period?: Record<string, number>
  price_source?: string
  missing_hours?: number
  coverage?: number
}
