import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ArrowRight,
  CalendarClock,
  CircleDollarSign,
  Gauge,
  Info,
  Lightbulb,
  Plug,
  RefreshCw,
  ShieldCheck,
  TrendingDown,
  Zap,
} from 'lucide-react'
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
import { api } from '../api'
import { DeviceIcon } from '../components/Icon'
import {
  Badge,
  Banner,
  Button,
  Card,
  EmptyState,
  ErrorBox,
  Loading,
  PeriodBar,
  PeriodLegend,
  Progress,
  QualityRing,
  Stat,
} from '../components/ui'
import { useApi } from '../hooks/useApi'
import {
  confidenceLabel,
  eur,
  formatDate,
  kwh,
  monthInputValue,
  pricePerKwh,
  pct,
  PERIOD_COLORS,
} from '../lib/format'
import type { Dashboard, PeriodId, Recommendation } from '../types'

export function DashboardPage({ onChanged }: { onChanged: () => Promise<void> }) {
  const navigate = useNavigate()
  const [month, setMonth] = useState(monthInputValue())
  const { data, loading, error, reload } = useApi<Dashboard>(`/dashboard?month=${month}`)
  const { data: recsData } = useApi<{ items: Recommendation[] }>('/recommendations')

  const topChart = useMemo(
    () =>
      (data?.top_devices ?? []).slice(0, 6).map((device) => ({
        name: device.name.length > 15 ? `${device.name.slice(0, 14)}…` : device.name,
        cost: Number(device.cost.toFixed(2)),
        color: PERIOD_COLORS.P3,
      })),
    [data],
  )

  if (loading && !data) return <Loading label="Calculando tu energía…" />
  if (error || !data) {
    return (
      <div className="page">
        <ErrorBox message={error ?? 'No se ha podido cargar el resumen'} />
        <Button className="mt-12" onClick={() => void reload()}>
          <RefreshCw size={14} /> Reintentar
        </Button>
      </div>
    )
  }

  const hasDevices = data.devices.length > 0
  const needsPrice = data.setup.needs_price || !data.price
  const priceFallback = data.price?.is_fallback
  const averagePrice = data.totals.energy_kwh > 0 ? data.totals.variable_cost / data.totals.energy_kwh : 0
  const fakePrice = needsPrice
  const recs = recsData?.items?.slice(0, 2) ?? []

  const refresh = async () => {
    await reload()
    await onChanged()
  }

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <div className="eyebrow">
            <Gauge size={12} /> Panel de energía
          </div>
          <h1 className="page-title">Tu energía, en claro.</h1>
          <p className="page-subtitle">
            Estimación de {data.month_label}. Consumo, coste por tramo y los aparatos que más pesan.
          </p>
        </div>
        <div className="actions">
          <input
            className="input"
            type="month"
            value={month}
            onChange={(event) => setMonth(event.target.value || monthInputValue())}
            style={{ width: 185 }}
            aria-label="Mes"
          />
          <Button onClick={() => void refresh()}>
            <RefreshCw size={14} /> Actualizar
          </Button>
          <Button variant="primary" onClick={() => navigate('/devices')}>
            <Plug size={14} /> Añadir dispositivo
          </Button>
        </div>
      </div>

      {needsPrice ? (
        <Banner tone="accent">
          <Zap size={15} style={{ flexShrink: 0, marginTop: 1 }} />
          <span>
            <strong>Faltan los precios de tu tarifa.</strong> Confirma los precios publicados por Pepe o
            introdúcelos manualmente para calcular costes.{' '}
            <button className="btn btn-sm btn-primary" style={{ marginLeft: 6 }} onClick={() => navigate('/tariff')}>
              Configurar precios <ArrowRight size={13} />
            </button>
          </span>
        </Banner>
      ) : priceFallback ? (
        <Banner tone="warning">
          <CalendarClock size={15} style={{ flexShrink: 0, marginTop: 1 }} />
          <span>
            <strong>Precio provisional.</strong> Se están usando los precios de {data.price?.month_label} para{' '}
            {data.month_label}. Pepe publica el mes pasado; confirma el precio definitivo en Tarifa.
          </span>
        </Banner>
      ) : null}

      {data.price_mode === 'hourly' && (data.totals.missing_hours ?? 0) > 0 ? (
        <Banner tone="warning">
          <Zap size={15} style={{ flexShrink: 0, marginTop: 1 }} />
          <span>
            <strong>PVPC incompleto.</strong> Faltan {data.totals.missing_hours} horas de precio para este
            mes; se usa el precio medio disponible. La estimación puede variar cuando REE publique el resto.
          </span>
        </Banner>
      ) : null}

      {data.contract.bono_social_category !== 'none' && !data.profile.bono_social_eligible ? (
        <Banner tone="warning">
          <Info size={15} style={{ flexShrink: 0, marginTop: 1 }} />
          <span>
            <strong>Bono social no aplicado.</strong> El descuento solo se aplica al PVPC. Con tu tarifa
            actual pagas la financiación regulada; el comparador muestra cuánto ahorrarías con PVPC.
          </span>
        </Banner>
      ) : null}

      <div className="hero mt-16">
        <div className="hero-content">
          <div>
            <div className="hero-kicker">
              <span>Factura estimada · {data.month_label}</span>
              {data.price ? (
                <Badge tone={priceFallback ? 'yellow' : 'green'}>
                  {data.price_mode === 'hourly'
                    ? 'PVPC horario'
                    : priceFallback
                      ? 'Provisional'
                      : 'Precio confirmado'}
                </Badge>
              ) : (
                <Badge tone="neutral">Sin precio</Badge>
              )}
              {data.price ? (
                <Badge tone="neutral">
                  {data.price.source === 'pepe_api'
                    ? 'Pepe API'
                    : data.price.source === 'ree_pvpc'
                      ? 'REE'
                      : 'Manual'}
                </Badge>
              ) : (
                <Badge tone="neutral">Sin precio</Badge>
              )}
              {data.profile.supports_pepephone_discount && data.contract.has_pepephone_discount ? (
                <Badge tone="green">Pepephone −4 €</Badge>
              ) : null}
              {(data.totals.bono_social_discount ?? 0) > 0 ? (
                <Badge tone="green">
                  Bono social −{eur(data.totals.bono_social_discount)}
                </Badge>
              ) : null}
            </div>
            <p className="hero-label">Total con potencia, cuotas e impuestos</p>
            <div className="hero-amount">
              {eur(data.totals.total)}
              <small>/mes</small>
            </div>
            <div className="hero-meta">
              <span>{kwh(data.totals.energy_kwh)} estimados</span>
              <span>{eur(data.totals.variable_cost)} de energía</span>
              <span>{eur(data.totals.fixed_total)} fijos e impuestos</span>
            </div>
          </div>
          <div className="hero-side">
            <div className="hero-actions">
              <Button variant="primary" onClick={() => navigate('/tariff')}>
                Ver tarifa <ArrowRight size={14} />
              </Button>
              <Button onClick={() => navigate('/schedule')}>
                <CalendarClock size={14} /> Horas baratas
              </Button>
            </div>
            <div className="flex gap-8" style={{ alignItems: 'center' }}>
              <QualityRing score={data.data_quality.score} label={data.data_quality.label} />
              <div className="small muted" style={{ maxWidth: 150 }}>
                <strong style={{ color: 'var(--text)' }}>Confianza {confidenceLabel(data.data_quality.label)}</strong>
                <br />
                {data.data_quality.calibrated
                  ? `Calibrada ×${data.data_quality.calibration_factor.toFixed(2)}`
                  : 'Sin calibrar con factura'}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="stat-grid mt-16">
        <Stat
          label="Consumo estimado"
          value={kwh(data.totals.energy_kwh)}
          meta={`${data.devices.length} aparatos activos`}
          icon={<Gauge size={15} />}
        />
        <Stat
          label="Coste variable"
          value={eur(data.totals.variable_cost)}
          meta={`${pricePerKwh(averagePrice)} de media`}
          icon={<TrendingDown size={15} />}
        />
        <Stat
          label="Coste fijo + impuestos"
          value={eur(data.totals.fixed_total)}
          meta="Potencia, cuotas, IVA e impuesto eléctrico"
          icon={<CircleDollarSign size={15} />}
        />
        <Stat
          label="Recomendaciones"
          value={data.recommendations_count}
          meta="Ideas de ahorro detectadas"
          icon={<Lightbulb size={15} />}
        />
      </div>

      {!hasDevices ? (
        <Card className="mt-16">
          <EmptyState
            icon={<Plug size={22} />}
            title="Añade tu primer aparato"
            text="Con la nevera, la vitro y la lavadora ya podemos empezar a estimar tu factura. No necesitas sensores."
            action={
              <Button variant="primary" onClick={() => navigate('/devices')}>
                <Plug size={14} /> Añadir dispositivo
              </Button>
            }
          />
        </Card>
      ) : (
        <div className="card-grid mt-16">
          <Card className="span-5">
            <div className="card-header">
              <div>
                <h2 className="card-title">Coste por tramo</h2>
                <p className="card-subtitle">
                  {data.price_mode === 'hourly'
                    ? 'En PVPC el precio cambia cada hora; aquí ves el reparto y el precio medio por tramo.'
                    : 'Cómo se reparte tu consumo entre valle, llano y punta.'}
                </p>
              </div>
              <PeriodLegend />
            </div>
            <div className="card-body">
              <div className="period-grid">
                {(data.by_period ?? []).map((period) => (
                  <div className="period-card" key={period.id}>
                    <div className="period-card-top">
                      <div className="period-name">
                        <span
                          className="period-dot"
                          style={{ background: PERIOD_COLORS[period.id as PeriodId] }}
                        />
                        {period.name}
                      </div>
                      <span className="small muted mono">{pricePerKwh(period.price)}</span>
                    </div>
                    <div className="period-cost">{eur(period.cost)}</div>
                    <div className="period-energy">{kwh(period.energy_kwh)}</div>
                    <div className="period-price">
                      {data.totals.energy_kwh > 0
                        ? pct((period.energy_kwh / data.totals.energy_kwh) * 100, 0)
                        : '0 %'}{' '}
                      del consumo
                    </div>
                  </div>
                ))}
              </div>
              <div className="mt-16">
                <PeriodBar
                  values={{
                    P1: data.by_period.find((p) => p.id === 'P1')?.energy_kwh ?? 0,
                    P2: data.by_period.find((p) => p.id === 'P2')?.energy_kwh ?? 0,
                    P3: data.by_period.find((p) => p.id === 'P3')?.energy_kwh ?? 0,
                  }}
                  height={9}
                />
              </div>
              {(data.totals.bono_social_discount ?? 0) > 0 ? (
                <div className="banner mt-12" style={{ background: 'var(--bg-soft)' }}>
                  <Info size={14} style={{ flexShrink: 0, marginTop: 1 }} />
                  <span>
                    El bono social (−{eur(data.totals.bono_social_discount)}) se aplica al total de la
                    factura; los costes por tramo y por dispositivo se muestran antes del descuento.
                  </span>
                </div>
              ) : null}
              <div className="between mt-12">
                <span className="small muted">
                  {needsPrice
                    ? 'Confirma los precios para ver el coste por tramo.'
                    : data.price_mode === 'hourly'
                      ? 'El coste real se calcula con la curva horaria; los precios mostrados son medias por tramo.'
                      : 'Los importes son coste de energía; los fijos se muestran aparte.'}
                </span>
                <Button size="sm" variant="ghost" onClick={() => navigate('/schedule')}>
                  Ver calendario <ArrowRight size={13} />
                </Button>
              </div>
            </div>
          </Card>

          <Card className="span-7">
            <div className="card-header">
              <div>
                <h2 className="card-title">Los que más gastan</h2>
                <p className="card-subtitle">Ranking por coste estimado en {data.month_label}.</p>
              </div>
              <Button size="sm" variant="ghost" onClick={() => navigate('/devices')}>
                Ver todos <ArrowRight size={13} />
              </Button>
            </div>
            <div className="card-body">
              <div className="device-list">
                {(data.top_devices ?? []).map((device) => (
                  <div className="device-row" key={device.id}>
                    <div className="device-icon">
                      <DeviceIcon name={device.icon} />
                    </div>
                    <div className="device-main">
                      <div className="device-name">{device.name}</div>
                      <div className="device-meta">
                        {device.area || 'Sin zona'} · {kwh(device.energy_kwh)} ·{' '}
                        {pct(device.share, 0)} del coste
                      </div>
                      <div className="mt-8" style={{ maxWidth: 320 }}>
                        <PeriodBar values={device.by_period} height={4} />
                      </div>
                    </div>
                    <div className="device-numbers">
                      <div className="device-cost">{eur(device.cost)}</div>
                      <div className="device-kwh">{confidenceLabel(device.confidence)}</div>
                    </div>
                  </div>
                ))}
              </div>
              {topChart.length > 0 ? (
                <div className="chart-box mt-16" aria-hidden="true">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={topChart} layout="vertical" margin={{ top: 0, right: 8, bottom: 0, left: 0 }}>
                      <CartesianGrid stroke="var(--border)" horizontal={false} />
                      <XAxis type="number" tickFormatter={(value) => `${value} €`} axisLine={false} tickLine={false} />
                      <YAxis
                        type="category"
                        dataKey="name"
                        width={95}
                        axisLine={false}
                        tickLine={false}
                        tick={{ fontSize: 10 }}
                      />
                      <Tooltip
                        formatter={(value) => [eur(Number(value)), 'Coste']}
                        contentStyle={{
                          background: 'var(--surface-3)',
                          border: '1px solid var(--border-strong)',
                          borderRadius: 10,
                          fontSize: 11,
                          color: 'var(--text)',
                        }}
                      />
                      <Bar dataKey="cost" radius={[0, 4, 4, 0]} barSize={9}>
                        {topChart.map((entry, index) => (
                          <Cell
                            key={`cell-${index}`}
                            fill={index === 0 ? 'var(--accent)' : 'rgba(198,242,78,0.45)'}
                          />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : null}
            </div>
          </Card>

          <Card className="span-5">
            <div className="card-header">
              <div>
                <h2 className="card-title">Horas más baratas</h2>
                <p className="card-subtitle">Trozo valle de los próximos días.</p>
              </div>
              <CalendarClock size={16} className="muted" />
            </div>
            <div className="card-body">
              <div className="cheap-list">
                {data.next_cheap_windows.map((window) => (
                  <div className="cheap-item" key={window.start}>
                    <span className="cheap-icon">
                      <Zap size={14} />
                    </span>
                    <div>
                      <div className="cheap-label">{window.label}</div>
                      <div className="cheap-meta">
                        {window.hours.toFixed(1)} h · {pricePerKwh(data.price?.p3_price ?? 0)}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
              <Button size="sm" variant="ghost" className="mt-12" onClick={() => navigate('/schedule')}>
                Abrir calendario <ArrowRight size={13} />
              </Button>
            </div>
          </Card>

          <Card className="span-7">
            <div className="card-header">
              <div>
                <h2 className="card-title">Recomendaciones para ahorrar</h2>
                <p className="card-subtitle">Lo más útil según tu consumo y tu tarifa.</p>
              </div>
              <Button size="sm" variant="ghost" onClick={() => navigate('/recommendations')}>
                Ver todas <ArrowRight size={13} />
              </Button>
            </div>
            <div className="card-body">
              {recs.length === 0 ? (
                <div className="small muted">
                  Todavía no hay recomendaciones. Añade dispositivos y confirma los precios.
                </div>
              ) : (
                <div style={{ display: 'grid', gap: 9 }}>
                  {recs.map((rec) => (
                    <div className={`recommendation ${rec.severity}`} key={rec.id}>
                      <div className="rec-top">
                        <h3 className="rec-title">{rec.title}</h3>
                        {rec.savings_eur_month > 0 ? (
                          <Badge tone="green">−{eur(rec.savings_eur_month)}/mes</Badge>
                        ) : (
                          <Badge tone={rec.severity === 'high' ? 'red' : 'blue'}>
                            {rec.severity === 'high' ? 'Alto' : 'Consejo'}
                          </Badge>
                        )}
                      </div>
                      <p className="rec-text">{rec.description}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </Card>

          <Card className="span-6">
            <div className="card-header">
              <div>
                <h2 className="card-title">Calidad del dato</h2>
                <p className="card-subtitle">Cuánto podemos fiarnos de la estimación.</p>
              </div>
              <ShieldCheck size={16} className="muted" />
            </div>
            <div className="card-body">
              <div className="between">
                <QualityRing score={data.data_quality.score} label={data.data_quality.label} />
                <div style={{ flex: 1, marginLeft: 18 }}>
                  <div className="between" style={{ marginBottom: 6 }}>
                    <span className="small">Confianza</span>
                    <strong>{confidenceLabel(data.data_quality.label)}</strong>
                  </div>
                  <Progress value={data.data_quality.score} />
                  <div className="small muted mt-8">
                    {data.data_quality.calibrated
                      ? `Factor de calibración ${data.data_quality.calibration_factor.toFixed(2)}. Ajustado con tu factura.`
                      : 'Calibra con tu última factura para acercar la estimación a la realidad.'}
                  </div>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="mt-8"
                    onClick={() => navigate('/tariff')}
                  >
                    Calibrar ahora <ArrowRight size={13} />
                  </Button>
                </div>
              </div>
            </div>
          </Card>

          <Card className="span-6">
            <div className="card-header">
              <div>
                <h2 className="card-title">Mercado eléctrico</h2>
                <p className="card-subtitle">Referencia ESIOS; no se aplica a tu tarifa de Pepe.</p>
              </div>
              <Badge tone={data.esios.connected ? 'green' : 'neutral'}>
                {data.esios.connected ? 'Conectado' : 'Opcional'}
              </Badge>
            </div>
            <div className="card-body">
              {data.esios.connected && data.esios.price !== null ? (
                <>
                  <div className="big-number">{pricePerKwh(data.esios.price)}</div>
                  <div className="small muted mt-8">
                    Precio actual de la entidad {data.esios.entity_id}. Es una referencia de mercado
                    {data.price_mode === 'hourly'
                      ? '; tu factura PVPC se calcula con la curva horaria de REE.'
                      : '; tu factura de Pepe usa los precios mensuales por tramo.'}
                  </div>
                </>
              ) : data.esios.configured ? (
                <div className="small muted">
                  La entidad ESIOS está configurada, pero Home Assistant no responde o no devuelve un
                  precio válido.
                </div>
              ) : (
                <div className="small muted">
                  Si tienes Conecta ESIOS, puedes seleccionar su sensor en Ajustes para ver aquí el precio
                  de mercado. Puedes comparar tu tarifa con PVPC en Tarifa → Comparador.
                  <div className="mt-12">
                    <Button size="sm" variant="ghost" onClick={() => navigate('/settings')}>
                      Configurar sensor <ArrowRight size={13} />
                    </Button>
                  </div>
                </div>
              )}
            </div>
          </Card>
        </div>
      )}

      <div className="small muted mt-16" style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <span>Estimación orientativa, no factura oficial.</span>
        <span>·</span>
        <span>Última actualización: {formatDate(new Date().toISOString())}</span>
        {fakePrice ? (
          <>
            <span>·</span>
            <span>Sin precios confirmados.</span>
          </>
        ) : null}
      </div>
    </div>
  )
}
