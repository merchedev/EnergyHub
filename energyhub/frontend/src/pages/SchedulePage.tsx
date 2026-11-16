import { useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ArrowRight,
  CalendarClock,
  Clock3,
  Info,
  Lightbulb,
  Sunrise,
  Zap,
} from 'lucide-react'
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { Badge, Banner, Button, Card, Loading, ErrorBox, PeriodLegend } from '../components/ui'
import { DeviceIcon } from '../components/Icon'
import { useApi } from '../hooks/useApi'
import { eur, kwh, pricePerKwh, pct } from '../lib/format'
import type { CalendarResponse, Device } from '../types'

function hoursOf(value: string): number {
  if (value === '24:00') return 24
  const [hours, minutes] = value.split(':').map(Number)
  return hours + (minutes || 0) / 60
}

function dayWidth(start: string, end: string): number {
  return ((hoursOf(end) - hoursOf(start)) / 24) * 100
}

export function SchedulePage() {
  const navigate = useNavigate()
  const { data, loading, error, reload } = useApi<CalendarResponse>('/tariff/calendar?days=7')
  const { data: devicesData } = useApi<{ items: Device[] }>('/devices')

  const flexible = useMemo(
    () =>
      (devicesData?.items ?? [])
        .filter((device) => device.flexibility !== 'none' && device.mode !== 'always_on')
        .sort((a, b) => b.energy_kwh - a.energy_kwh)
        .slice(0, 5),
    [devicesData],
  )

  const hourlyChart = useMemo(
    () =>
      (data?.hourly?.points ?? []).slice(0, 48).map((point) => {
        const date = new Date(point.timestamp)
        return {
          label: new Intl.DateTimeFormat('es-ES', {
            weekday: 'short',
            hour: '2-digit',
            minute: '2-digit',
          }).format(date),
          price: point.missing ? null : Number(point.price.toFixed(4)),
          missing: point.missing,
        }
      }),
    [data],
  )

  if (loading && !data) return <Loading label="Preparando el calendario…" />
  if (error && !data) return <ErrorBox message={error} />
  if (!data) return null

  const cheapest = data.cheap_windows[0]

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <div className="eyebrow">
            <CalendarClock size={12} /> Horarios
          </div>
          <h1 className="page-title">La energía barata tiene horario.</h1>
          <p className="page-subtitle">
            {data.price_mode === 'hourly'
              ? 'Tu tarifa PVPC cambia cada hora. Aquí tienes la curva de precio, las mejores ventanas y el planificador de cargas flexibles.'
              : 'Con tu tarifa por tramos, el precio depende de valle/llano/punta. Aquí tienes el calendario y las mejores ventanas para las cargas flexibles.'}
          </p>
        </div>
        <div className="actions">
          <Button onClick={() => void reload()}>
            <CalendarClock size={14} /> Actualizar
          </Button>
          <Button variant="primary" onClick={() => navigate('/recommendations')}>
            <Lightbulb size={14} /> Recomendaciones
          </Button>
        </div>
      </div>

      {data.price?.is_fallback ? (
        <Banner tone="warning">
          <Info size={15} style={{ flexShrink: 0, marginTop: 1 }} />
          <span>
            Los precios de {data.price.month_label} son provisionales para este mes. Las ventanas valle no
            cambian, pero el importe puede ajustarse cuando Pepe publique el mes actual.
          </span>
        </Banner>
      ) : null}

      {data.price_mode === 'hourly' ? (
        <>
          <Banner tone="accent">
            <Zap size={15} style={{ flexShrink: 0, marginTop: 1 }} />
            <span>
              <strong>PVPC horario.</strong> Precios de REE para las próximas 48 h. El importe de cada hora
              se aplica a tu consumo estimado en esa hora.
              {data.hourly && data.hourly.missing_hours > 0
                ? ` REE aún no ha publicado ${data.hourly.missing_hours} horas; la curva muestra solo las disponibles.`
                : ''}
            </span>
          </Banner>
          {hourlyChart.length > 0 ? (
            <Card className="mt-16">
              <div className="card-header">
                <div>
                  <h2 className="card-title">Precio PVPC por hora</h2>
                  <p className="card-subtitle">Próximas 48 h · €/kWh</p>
                </div>
                <Badge tone="green">Horario</Badge>
              </div>
              <div className="card-body">
                <div className="chart-box" style={{ height: 240 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={hourlyChart} margin={{ top: 10, right: 8, left: 0, bottom: 0 }}>
                      <defs>
                        <linearGradient id="pvpcFill" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="var(--accent)" stopOpacity={0.35} />
                          <stop offset="100%" stopColor="var(--accent)" stopOpacity={0.01} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid stroke="var(--border)" vertical={false} />
                      <XAxis
                        dataKey="label"
                        axisLine={false}
                        tickLine={false}
                        interval={5}
                        tick={{ fontSize: 10 }}
                      />
                      <YAxis
                        axisLine={false}
                        tickLine={false}
                        tick={{ fontSize: 10 }}
                        tickFormatter={(value) => `${Number(value).toFixed(2)}`}
                      />
                      <Tooltip
                        formatter={(value) => [pricePerKwh(Number(value)), 'PVPC']}
                        contentStyle={{
                          background: 'var(--surface-3)',
                          border: '1px solid var(--border-strong)',
                          borderRadius: 10,
                          fontSize: 11,
                          color: 'var(--text)',
                        }}
                      />
                      <Area
                        type="monotone"
                        dataKey="price"
                        stroke="var(--accent)"
                        strokeWidth={2}
                        fill="url(#pvpcFill)"
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </Card>
          ) : null}
        </>
      ) : null}

      <div className="card-grid mt-16">
        <Card className="span-8">
          <div className="card-header">
            <div>
              <h2 className="card-title">Próximos 7 días</h2>
              <p className="card-subtitle">
                {data.price_mode === 'hourly'
                  ? 'Tramos 2.0TD con el precio medio de cada periodo.'
                  : 'Cada barra representa las 24 h del día.'}
              </p>
            </div>
            <PeriodLegend />
          </div>
          <div className="card-body">
            <div className="calendar">
              {data.days.map((day) => (
                <div className={`calendar-day ${day.is_today ? 'today' : ''}`} key={day.date}>
                  <div className="day-head">
                    <div>
                      <div className="day-name">{day.is_today ? 'Hoy' : day.weekday}</div>
                      <div className="day-num">{day.day}</div>
                    </div>
                    {day.is_holiday ? <Badge tone="green">Festivo</Badge> : null}
                  </div>
                  <div className="day-bar">
                    {day.windows.map((window) => (
                      <span
                        key={`${day.date}-${window.start}-${window.id}`}
                        title={`${window.start}–${window.end} · ${window.name} · ${pricePerKwh(window.price)}`}
                        style={{
                          width: `${dayWidth(window.start, window.end)}%`,
                          background:
                            window.id === 'P1'
                              ? 'var(--p1)'
                              : window.id === 'P2'
                                ? 'var(--p2)'
                                : 'var(--p3)',
                          opacity: window.id === 'P3' ? 1 : 0.8,
                        }}
                      />
                    ))}
                  </div>
                  <div className="hour-labels">
                    <span>0h</span>
                    <span>6h</span>
                    <span>12h</span>
                    <span>18h</span>
                    <span>24h</span>
                  </div>
                </div>
              ))}
            </div>
            <div className="small muted mt-12">
              El tramo valle es de 00:00 a 08:00 de lunes a viernes y todo el día en fines de semana y
              festivos nacionales. Los festivos se calculan según la comunidad configurada en Tarifa.
            </div>
          </div>
        </Card>

        <Card className="span-4">
          <div className="card-header">
            <div>
              <h2 className="card-title">Mejores ventanas</h2>
              <p className="card-subtitle">Tramos valle próximos.</p>
            </div>
            <Sunrise size={17} className="muted" />
          </div>
          <div className="card-body">
            <div className="cheap-list">
              {data.cheap_windows.map((window) => (
                <div className="cheap-item" key={window.start}>
                  <span className="cheap-icon">
                    <Zap size={14} />
                  </span>
                  <div>
                    <div className="cheap-label">{window.label}</div>
                    <div className="cheap-meta">
                      {window.hours.toFixed(1)} h ·{' '}
                      {pricePerKwh(window.average_price ?? data.price?.p3_price ?? 0)}
                    </div>
                  </div>
                </div>
              ))}
            </div>
            {cheapest ? (
              <div className="banner accent mt-16">
                <Clock3 size={15} style={{ flexShrink: 0, marginTop: 1 }} />
                <span>
                  La próxima ventana más barata es <strong>{cheapest.label}</strong>. Es el mejor momento
                  para lavadora, lavavajillas, secadora o coche eléctrico.
                </span>
              </div>
            ) : null}
          </div>
        </Card>
      </div>

      <Card className="mt-16">
        <div className="card-header">
          <div>
            <h2 className="card-title">Planificador de cargas flexibles</h2>
            <p className="card-subtitle">
              Aparatos que puedes mover a valle sin cambiar tu rutina. Los que no son flexibles no aparecen.
            </p>
          </div>
          <Badge tone="neutral">{flexible.length} flexibles</Badge>
        </div>
        <div className="card-body">
          {flexible.length === 0 ? (
            <div className="small muted">
              Aún no hay aparatos marcados como flexibles. Edita la lavadora, el lavavajillas o el coche
              eléctrico y elige “Flexible” para ver recomendaciones.
            </div>
          ) : (
            <div style={{ display: 'grid', gap: 9 }}>
              {flexible.map((device) => {
                const shiftable = device.by_period.P1 + device.by_period.P2
                return (
                  <div className="device-row" key={device.id}>
                    <div className="device-icon">
                      <DeviceIcon name={device.icon} />
                    </div>
                    <div className="device-main">
                      <div className="device-name">{device.name}</div>
                      <div className="device-meta">
                        {device.flexibility === 'flexible' ? 'Flexible' : 'Semi-flexible'} ·{' '}
                        {shiftable > 0
                          ? `${kwh(shiftable)} en punta/llano`
                          : 'Ya está casi todo en valle'}
                        {device.cycles_per_week > 0
                          ? ` · ${device.cycles_per_week} ciclos/semana`
                          : ` · ${device.hours_per_day} h/día`}
                      </div>
                    </div>
                    <div className="device-numbers">
                      <div className="device-cost">{eur(device.cost)}</div>
                      <div className="device-kwh">{pct(device.share, 0)} del total</div>
                    </div>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => navigate('/recommendations')}
                      className="hide-mobile"
                    >
                      Ver acción <ArrowRight size={13} />
                    </Button>
                  </div>
                )
              })}
            </div>
          )}
          <div className="banner mt-16">
            <Info size={15} style={{ flexShrink: 0, marginTop: 1 }} />
            <span>
              {data.price_mode === 'hourly'
                ? 'Con PVPC, la app busca la ventana más barata de las próximas horas. No te dirá que pongas la vitro a las 3 de la mañana: solo mueve cargas que realmente puedas programar. Puedes comparar Pepe y PVPC en Tarifa → Comparador.'
                : 'Con la tarifa de Pepe, todas las horas de valle valen lo mismo. La app no te dirá que pongas la vitro a las 3 de la mañana: solo mueve cargas que realmente puedas programar. Puedes comparar Pepe y PVPC en Tarifa → Comparador.'}
            </span>
          </div>
        </div>
      </Card>
    </div>
  )
}
