import type { Confidence, DeviceMode, Flexibility, PeriodId } from '../types'

export const PERIOD_COLORS: Record<PeriodId, string> = {
  P1: '#ff7a59',
  P2: '#f5c84b',
  P3: '#55d98a',
}

export const PERIOD_LABELS: Record<PeriodId, string> = {
  P1: 'Punta',
  P2: 'Llano',
  P3: 'Valle',
}

export function cn(...values: Array<string | false | null | undefined>): string {
  return values.filter(Boolean).join(' ')
}

export function eur(value: number | null | undefined, digits = 2): string {
  const number = Number(value ?? 0)
  return new Intl.NumberFormat('es-ES', {
    style: 'currency',
    currency: 'EUR',
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(Number.isFinite(number) ? number : 0)
}

export function kwh(value: number | null | undefined, digits = 1): string {
  const number = Number(value ?? 0)
  return `${new Intl.NumberFormat('es-ES', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(Number.isFinite(number) ? number : 0)} kWh`
}

export function watts(value: number | null | undefined): string {
  const number = Number(value ?? 0)
  if (number >= 1000) {
    return `${new Intl.NumberFormat('es-ES', { maximumFractionDigits: 1 }).format(number / 1000)} kW`
  }
  return `${new Intl.NumberFormat('es-ES', { maximumFractionDigits: 0 }).format(number)} W`
}

export function pct(value: number | null | undefined, digits = 0): string {
  return `${new Intl.NumberFormat('es-ES', { maximumFractionDigits: digits }).format(Number(value ?? 0))} %`
}

export function pricePerKwh(value: number | null | undefined): string {
  return `${new Intl.NumberFormat('es-ES', {
    minimumFractionDigits: 3,
    maximumFractionDigits: 3,
  }).format(Number(value ?? 0))} €/kWh`
}

export function pricePerKwDay(value: number | null | undefined): string {
  return `${new Intl.NumberFormat('es-ES', {
    minimumFractionDigits: 3,
    maximumFractionDigits: 4,
  }).format(Number(value ?? 0))} €/kW/día`
}

export function confidenceLabel(value: Confidence): string {
  return value === 'alta' ? 'Alta' : value === 'media' ? 'Media' : 'Baja'
}

export function modeLabel(mode: DeviceMode): string {
  const labels: Record<DeviceMode, string> = {
    always_on: 'Siempre enchufado',
    hours_per_day: 'Horas al día',
    cycles: 'Por ciclos',
    entity: 'Entidad de HA',
  }
  return labels[mode]
}

export function flexibilityLabel(value: Flexibility): string {
  return value === 'flexible' ? 'Flexible' : value === 'semi' ? 'Semi-flexible' : 'No flexible'
}

export function monthInputValue(date = new Date()): string {
  const year = date.getFullYear()
  const month = `${date.getMonth() + 1}`.padStart(2, '0')
  return `${year}-${month}`
}

export function monthTitle(value: string | null | undefined): string {
  if (!value) return ''
  const [year, month] = value.split('-').map(Number)
  if (!year || !month) return value
  return new Intl.DateTimeFormat('es-ES', { month: 'long', year: 'numeric' }).format(
    new Date(year, month - 1, 1),
  )
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('es-ES', { day: 'numeric', month: 'short', year: 'numeric' }).format(date)
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('es-ES', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

export function shortMonth(value: string | null | undefined): string {
  if (!value) return ''
  const [year, month] = value.split('-').map(Number)
  if (!year || !month) return value
  return new Intl.DateTimeFormat('es-ES', { month: 'short' }).format(new Date(year, month - 1, 1))
}
