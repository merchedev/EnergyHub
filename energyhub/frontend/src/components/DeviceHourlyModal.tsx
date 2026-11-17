import { useEffect, useMemo, useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { ArrowRight, Clock3, Info, Zap } from 'lucide-react'
import { useApi } from '../hooks/useApi'
import {
  Badge,
  Banner,
  Button,
  ErrorBox,
  Loading,
  Modal,
  PeriodBar,
  PeriodLegend,
  Select,
  Stat,
  Tabs,
} from './ui'
import {
  PERIOD_COLORS,
  PERIOD_LABELS,
  eur,
  kwh,
  monthInputValue,
  monthTitle,
  pct,
  pricePerKwh,
} from '../lib/format'
import type { Device, DeviceHourlyResponse, PeriodId } from '../types'

type View = 'profile' | 'day'

const TOOLTIP_STYLE = {
  background: 'var(--surface-3)',
  border: '1px solid var(--border-strong)',
  borderRadius: 10,
  fontSize: 11,
  color: 'var(--text)',
}

function dayLabel(value: string): string {
  if (!value) return ''
  const [year, month, day] = value.split('-').map(Number)
  if (!year || !month || !day) return value
  return new Intl.DateTimeFormat('es-ES', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
  }).format(new Date(year, month - 1, day))
}

function hourLabel(hour: number): string {
  return `${String(hour).padStart(2, '0')}:00`
}

function hourRange(hour: number): string {
  return `${String(hour).padStart(2, '0')}:00–${String(hour + 1).padStart(2, '0')}:00`
}

function resolutionLabel(value: DeviceHourlyResponse['energy_resolution']): string {
  return value === 'hourly'
    ? 'Consumo real por hora'
    : value === 'monthly'
      ? 'Total real · reparto estimado'
      : 'Estimación por potencia, horas o ciclos'
}

export function DeviceHourlyModal({ device, onClose }: { device: Device; onClose: () => void }) {
  const [month, setMonth] = useState(monthInputValue())
  const [view, setView] = useState<View>('profile')
  const [selectedDate, setSelectedDate] = useState('')
  const { data, loading, error } = useApi<DeviceHourlyResponse>(
    `/devices/${device.id}/hourly?month=${month}`,
  )

  const days = data?.days ?? []
  const topDay = useMemo(() => {
    const best = [...days].sort((a, b) => b.energy_kwh - a.energy_kwh)[0]
    return best && best.energy_kwh > 0 ? best : null
  }, [days])

  useEffect(() => {
    if (selectedDate && days.some((day) => day.date === selectedDate)) return
    setSelectedDate(topDay?.date ?? days[0]?.date ?? '')
  }, [days, selectedDate, topDay])

  const profile = useMemo(
    () =>
      (data?.profile ?? []).map((row) => ({
        ...row,
        label: hourLabel(row.hour),
        total: row.energy_kwh,
      })),
    [data],
  )

  const topHour = useMemo(() => {
    const best = [...profile].sort((a, b) => b.total - a.total)[0]
    return best && best.total > 0 ? best : null
  }, [profile])

  const selectedDay = days.find((day) => day.date === selectedDate) ?? null
  const dayHours = useMemo(() => {
    const byHour = new Map<number, { energy_kwh: number; cost_eur: number; period: PeriodId }>()
    for (const item of data?.hours ?? []) {
      if (item.date !== selectedDate) continue
      const previous = byHour.get(item.hour)
      byHour.set(item.hour, {
        energy_kwh: (previous?.energy_kwh ?? 0) + item.energy_kwh,
        cost_eur: (previous?.cost_eur ?? 0) + item.cost_eur,
        period: previous?.period ?? item.period,
      })
    }
    return Array.from({ length: 24 }, (_, hour) => {
      const item = byHour.get(hour)
      return {
        hour,
        label: hourLabel(hour),
        energy_kwh: item?.energy_kwh ?? 0,
        cost_eur: item?.cost_eur ?? 0,
        period: item?.period ?? null,
      }
    })
  }, [data, selectedDate])

  const periodValues = useMemo(() => {
    const values: Record<PeriodId, number> = { P1: 0, P2: 0, P3: 0 }
    for (const period of data?.periods ?? []) values[period.id] = period.energy_kwh
    return values
  }, [data])

  const topPeriod = data?.top_period ?? null
  const subtitle = data
    ? `${data.month_label} · ${resolutionLabel(data.energy_resolution)}`
    : `${monthTitle(month)} · leyendo consumo…`

  return (
    <Modal
      open
      onClose={onClose}
      title={`Consumo por hora · ${device.name}`}
      subtitle={subtitle}
      size="lg"
    >
      {loading && !data ? (
        <Loading label="Leyendo el consumo por hora…" />
      ) : error ? (
        <ErrorBox message={error} />
      ) : !data ? null : (
        <>
          <div className="between" style={{ gap: 12, flexWrap: 'wrap' }}>
            <Tabs
              value={view}
              onChange={setView}
              options={[
                { value: 'profile', label: 'Perfil del mes' },
                { value: 'day', label: 'Por día' },
              ]}
            />
            <div className="flex gap-8" style={{ flexWrap: 'wrap', alignItems: 'center' }}>
              {loading && data ? <Badge tone="neutral">Actualizando…</Badge> : null}
              {view === 'day' && days.length > 0 ? (
                <Select
                  value={selectedDate}
                  onChange={(event) => setSelectedDate(event.target.value)}
                  style={{ width: 200, minWidth: 185 }}
                  aria-label="Día"
                >
                  {days.map((day) => (
                    <option key={day.date} value={day.date}>
                      {dayLabel(day.date)} · {kwh(day.energy_kwh, 2)}
                    </option>
                  ))}
                </Select>
              ) : null}
              <input
                className="input"
                type="month"
                value={month}
                onChange={(event) => setMonth(event.target.value || monthInputValue())}
                style={{ width: 165 }}
                aria-label="Mes"
              />
            </div>
          </div>

          <div className="stat-grid mt-16">
            <Stat
              label="Consumo"
              value={kwh(data.energy_kwh, 2)}
              meta={data.month_label}
              icon={<Zap size={15} />}
            />
            <Stat
              label="Coste energía"
              value={data.price_source ? eur(data.cost_eur) : '—'}
              meta={data.price_source ? 'Con los precios del mes' : 'Sin precios confirmados'}
            />
            <Stat
              label="Tramo más usado"
              value={
                topPeriod ? (
                  <span style={{ color: PERIOD_COLORS[topPeriod.id] }}>
                    {PERIOD_LABELS[topPeriod.id]}
                  </span>
                ) : (
                  '—'
                )
              }
              meta={
                topPeriod
                  ? `${kwh(topPeriod.energy_kwh, 2)} · ${pct(topPeriod.share, 0)} del consumo`
                  : 'Sin consumo en el mes'
              }
            />
            <Stat
              label="Hora de más consumo"
              value={topHour ? hourRange(topHour.hour) : '—'}
              meta={topHour ? kwh(topHour.total, 2) : 'Sin consumo en el mes'}
              icon={<Clock3 size={15} />}
            />
          </div>

          {topDay ? (
            <div className="between mt-8" style={{ gap: 8 }}>
              <div className="small muted">
                Día de más consumo: <strong>{dayLabel(topDay.date)}</strong> · {kwh(topDay.energy_kwh, 2)}
              </div>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => {
                  setView('day')
                  setSelectedDate(topDay.date)
                }}
              >
                Ver día <ArrowRight size={13} />
              </Button>
            </div>
          ) : null}

          {data.price_is_fallback ? (
            <Banner tone="warning">
              <Info size={15} style={{ flexShrink: 0, marginTop: 1 }} />
              <span>
                Se usan los precios de{' '}
                {data.price_reference_month ? monthTitle(data.price_reference_month) : 'un mes anterior'}{' '}
                como provisionales para {data.month_label}. Confirma la tarifa del mes actual para ajustar
                el coste.
              </span>
            </Banner>
          ) : null}

          {!data.price_source ? (
            <Banner tone="warning">
              <Info size={15} style={{ flexShrink: 0, marginTop: 1 }} />
              <span>
                No hay precios confirmados para {data.month_label}. El consumo se calcula, pero el coste
                aparecerá cuando configures la tarifa.
              </span>
            </Banner>
          ) : null}

          {data.energy_resolution === 'hourly' ? (
            <Banner tone="accent">
              <Zap size={15} style={{ flexShrink: 0, marginTop: 1 }} />
              <span>
                Consumo real por hora de Home Assistant. El reparto por tramos y el coste usan la energía
                de cada hora.
              </span>
            </Banner>
          ) : data.energy_resolution === 'monthly' ? (
            <Banner tone="warning">
              <Info size={15} style={{ flexShrink: 0, marginTop: 1 }} />
              <span>
                El total del mes es real, pero el reparto por horas es una estimación con la franja típica
                del aparato.
              </span>
            </Banner>
          ) : (
            <Banner tone="accent">
              <Info size={15} style={{ flexShrink: 0, marginTop: 1 }} />
              <span>
                Consumo estimado a partir de la potencia y las horas o ciclos configurados para el aparato.
              </span>
            </Banner>
          )}

          {data.hours.length === 0 ? (
            <Banner tone="warning">
              <Info size={15} style={{ flexShrink: 0, marginTop: 1 }} />
              <span>No hay consumo registrado para {data.month_label}.</span>
            </Banner>
          ) : (
            <div className="card mt-16">
              <div className="card-header">
                <div>
                  <h2 className="card-title">
                    {view === 'profile'
                      ? 'Perfil por hora del mes'
                      : `Consumo por hora · ${selectedDay ? dayLabel(selectedDay.date) : ''}`}
                  </h2>
                  <p className="card-subtitle">
                    {view === 'profile'
                      ? 'Energía acumulada en cada hora del día. El color indica el tramo tarifario.'
                      : 'Energía de cada hora del día seleccionado.'}
                  </p>
                </div>
                <PeriodLegend />
              </div>
              <div className="card-body">
                <div className="chart-box" style={{ height: 270 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    {view === 'profile' ? (
                      <BarChart data={profile} margin={{ top: 10, right: 8, left: 0, bottom: 0 }}>
                        <CartesianGrid stroke="var(--border)" vertical={false} />
                        <XAxis
                          dataKey="hour"
                          tickFormatter={(value) => hourLabel(Number(value))}
                          axisLine={false}
                          tickLine={false}
                          interval={2}
                          tick={{ fontSize: 10 }}
                        />
                        <YAxis
                          axisLine={false}
                          tickLine={false}
                          tick={{ fontSize: 10 }}
                          tickFormatter={(value) => Number(value).toFixed(2)}
                          width={42}
                        />
                        <Tooltip
                          formatter={(value) => kwh(Number(value), 3)}
                          labelFormatter={(label) => hourRange(Number(label))}
                          contentStyle={TOOLTIP_STYLE}
                        />
                        <Bar dataKey="P1" stackId="a" fill={PERIOD_COLORS.P1} name={PERIOD_LABELS.P1} />
                        <Bar dataKey="P2" stackId="a" fill={PERIOD_COLORS.P2} name={PERIOD_LABELS.P2} />
                        <Bar dataKey="P3" stackId="a" fill={PERIOD_COLORS.P3} name={PERIOD_LABELS.P3} />
                      </BarChart>
                    ) : (
                      <BarChart data={dayHours} margin={{ top: 10, right: 8, left: 0, bottom: 0 }}>
                        <CartesianGrid stroke="var(--border)" vertical={false} />
                        <XAxis
                          dataKey="hour"
                          tickFormatter={(value) => hourLabel(Number(value))}
                          axisLine={false}
                          tickLine={false}
                          interval={2}
                          tick={{ fontSize: 10 }}
                        />
                        <YAxis
                          axisLine={false}
                          tickLine={false}
                          tick={{ fontSize: 10 }}
                          tickFormatter={(value) => Number(value).toFixed(2)}
                          width={42}
                        />
                        <Tooltip
                          formatter={(value) => kwh(Number(value), 3)}
                          labelFormatter={(label) => hourRange(Number(label))}
                          contentStyle={TOOLTIP_STYLE}
                        />
                        <Bar dataKey="energy_kwh" name="Consumo" radius={[3, 3, 0, 0]}>
                          {dayHours.map((entry) => (
                            <Cell
                              key={entry.hour}
                              fill={entry.period ? PERIOD_COLORS[entry.period] : 'var(--border)'}
                            />
                          ))}
                        </Bar>
                      </BarChart>
                    )}
                  </ResponsiveContainer>
                </div>
                {view === 'day' && selectedDay ? (
                  <div className="between mt-8 small muted">
                    <span>Color = tramo tarifario</span>
                    <span>
                      {kwh(selectedDay.energy_kwh, 2)} · {eur(selectedDay.cost_eur)}
                    </span>
                  </div>
                ) : null}
              </div>
            </div>
          )}

          <div className="card mt-16">
            <div className="card-header">
              <div>
                <h2 className="card-title">Reparto por tramo</h2>
                <p className="card-subtitle">
                  {topPeriod
                    ? `Has usado más el tramo ${PERIOD_LABELS[topPeriod.id].toLowerCase()} (${pct(
                        topPeriod.share,
                        0,
                      )} del consumo).`
                    : 'Sin consumo registrado en el mes.'}
                </p>
              </div>
              <PeriodLegend />
            </div>
            <div className="card-body">
              <div className="period-grid">
                {data.periods.map((period) => (
                  <div
                    className="period-card"
                    key={period.id}
                    style={
                      topPeriod?.id === period.id
                        ? { borderColor: PERIOD_COLORS[period.id] }
                        : undefined
                    }
                  >
                    <div className="period-card-top">
                      <div className="period-name">
                        <span
                          className="period-dot"
                          style={{ background: PERIOD_COLORS[period.id] }}
                        />
                        {PERIOD_LABELS[period.id]}
                      </div>
                      {topPeriod?.id === period.id ? (
                        <Badge tone="green">Más usado</Badge>
                      ) : (
                        <span className="small muted mono">{pricePerKwh(period.price)}</span>
                      )}
                    </div>
                    <div className="period-cost">{eur(period.cost_eur)}</div>
                    <div className="period-energy">{kwh(period.energy_kwh, 2)}</div>
                    <div className="period-price">
                      {pct(period.share, 0)} del consumo · {pricePerKwh(period.price)}
                    </div>
                  </div>
                ))}
              </div>
              <div className="mt-16">
                <PeriodBar values={periodValues} />
              </div>
            </div>
          </div>

          {data.notes.length > 0 ? (
            <div className="small muted mt-12">
              {data.notes.slice(0, 3).map((note) => (
                <div key={note}>· {note}</div>
              ))}
            </div>
          ) : null}
        </>
      )}
    </Modal>
  )
}
