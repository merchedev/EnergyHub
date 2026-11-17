import { useMemo, useState } from 'react'
import {
  BarChart3,
  ChevronRight,
  Gauge,
  Home,
  Plug,
  Search,
  Sparkles,
  Wallet,
  Zap,
} from 'lucide-react'
import { api } from '../api'
import { DeviceIcon } from '../components/Icon'
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorBox,
  Loading,
  PeriodBar,
  Stat,
} from '../components/ui'
import { useApi } from '../hooks/useApi'
import {
  confidenceLabel,
  eur,
  kwh,
  modeLabel,
  pct,
  watts,
} from '../lib/format'
import type { CatalogItem, Device } from '../types'
import { DeviceHourlyModal } from '../components/DeviceHourlyModal'
import { DeviceForm } from './DeviceForm'

export function DevicesPage() {
  const { data, loading, error, reload } = useApi<{
    items: Device[]
    summary: { energy_kwh: number; cost: number; count: number }
  }>('/devices')
  const { data: catalogData } = useApi<{ items: CatalogItem[] }>('/catalog')
  const [search, setSearch] = useState('')
  const [formOpen, setFormOpen] = useState(false)
  const [editing, setEditing] = useState<Device | null>(null)
  const [initialCategory, setInitialCategory] = useState<string | null>(null)
  const [hourlyDevice, setHourlyDevice] = useState<Device | null>(null)

  const catalog = catalogData?.items ?? []
  const devices = data?.items ?? []

  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase()
    if (!query) return devices
    return devices.filter(
      (device) =>
        device.name.toLowerCase().includes(query) ||
        (device.area ?? '').toLowerCase().includes(query) ||
        device.category.toLowerCase().includes(query),
    )
  }, [devices, search])

  const topDevice = useMemo(
    () => [...devices].sort((a, b) => b.cost - a.cost)[0] ?? null,
    [devices],
  )

  const openNew = (category?: string) => {
    setEditing(null)
    setInitialCategory(category ?? null)
    setFormOpen(true)
  }

  const openEdit = (device: Device) => {
    setEditing(device)
    setInitialCategory(null)
    setFormOpen(true)
  }

  if (loading && !data) return <Loading label="Cargando dispositivos…" />
  if (error && !data) return <ErrorBox message={error} />

  const popular = ['fridge', 'vitro', 'washing_machine', 'tv', 'router', 'other']
    .map((id) => catalog.find((item) => item.id === id))
    .filter(Boolean) as CatalogItem[]

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <div className="eyebrow">
            <Plug size={12} /> Inventario
          </div>
          <h1 className="page-title">Dispositivos</h1>
          <p className="page-subtitle">
            Añade cualquier aparato enchufado a la red. Con potencia y horas o ciclos ya podemos estimar su
            consumo.
          </p>
        </div>
        <div className="actions">
          <Button variant="primary" onClick={() => openNew()}>
            <Plug size={14} /> Añadir dispositivo
          </Button>
        </div>
      </div>

      <div className="stat-grid">
        <Stat
          label="Dispositivos"
          value={devices.length}
          meta={`${devices.filter((device) => device.enabled).length} activos`}
          icon={<Plug size={15} />}
        />
        <Stat
          label="Consumo estimado"
          value={kwh(data?.summary.energy_kwh ?? 0)}
          meta="Este mes"
          icon={<Gauge size={15} />}
        />
        <Stat
          label="Coste energía"
          value={eur(data?.summary.cost ?? 0)}
          meta="Antes de fijos e impuestos"
          icon={<Wallet size={15} />}
        />
        <Stat
          label="Mayor consumidor"
          value={topDevice ? topDevice.name : '—'}
          meta={topDevice ? `${eur(topDevice.cost)} · ${pct(topDevice.share, 0)}` : 'Añade un aparato'}
          icon={<Zap size={15} />}
        />
      </div>

      {devices.length === 0 ? (
        <Card className="mt-16">
          <EmptyState
            icon={<Home size={22} />}
            title="Todavía no hay aparatos"
            text="Empieza por los que más gastan. La app trae valores típicos para que solo tengas que ajustar lo que sepas."
            action={
              <div className="flex gap-8" style={{ flexWrap: 'wrap', justifyContent: 'center' }}>
                {popular.slice(0, 4).map((item) => (
                  <Button key={item.id} onClick={() => openNew(item.id)}>
                    <DeviceIcon name={item.icon} size={15} /> {item.name}
                  </Button>
                ))}
              </div>
            }
          />
        </Card>
      ) : (
        <>
          <div className="between mt-16" style={{ gap: 12, flexWrap: 'wrap' }}>
            <div className="flex gap-8" style={{ flexWrap: 'wrap' }}>
              <Badge tone="neutral">{devices.length} aparatos</Badge>
              <Badge tone="green">Sin sensores obligatorios</Badge>
            </div>
            <div style={{ position: 'relative', width: 'min(280px, 100%)' }}>
              <Search
                size={14}
                style={{
                  position: 'absolute',
                  left: 11,
                  top: '50%',
                  transform: 'translateY(-50%)',
                  color: 'var(--muted)',
                }}
              />
              <input
                className="input"
                style={{ paddingLeft: 32 }}
                placeholder="Buscar aparato o zona…"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
              />
            </div>
          </div>

          {filtered.length === 0 ? (
            <Card className="mt-12">
              <EmptyState
                icon={<Search size={21} />}
                title="Sin resultados"
                text={`No hay dispositivos que coincidan con “${search}”.`}
                action={
                  <Button variant="ghost" onClick={() => setSearch('')}>
                    Limpiar búsqueda
                  </Button>
                }
              />
            </Card>
          ) : (
            <div className="card-grid mt-12">
              {filtered.map((device) => (
                <Card className="span-6" key={device.id}>
                  <div className="card-body">
                    <div className="between" style={{ alignItems: 'flex-start' }}>
                      <div className="flex gap-12" style={{ minWidth: 0 }}>
                        <div className="device-icon" style={{ width: 42, height: 42 }}>
                          <DeviceIcon name={device.icon} size={21} />
                        </div>
                        <div style={{ minWidth: 0 }}>
                          <div className="device-name" style={{ fontSize: 14 }}>
                            {device.name}
                          </div>
                          <div className="device-meta">
                            {device.area || 'Sin zona'} · {modeLabel(device.mode)}
                          </div>
                          <div className="flex gap-8 mt-8" style={{ flexWrap: 'wrap' }}>
                            <Badge tone={device.confidence === 'alta' ? 'green' : device.confidence === 'media' ? 'yellow' : 'red'}>
                              {confidenceLabel(device.confidence)}
                            </Badge>
                            {device.is_demo ? <Badge tone="blue">Demo</Badge> : null}
                            {device.energy_source === 'ha_energy_sensor' ? (
                              <Badge tone="green">
                                {device.energy_resolution === 'hourly'
                                  ? 'Consumo real horario'
                                  : 'Consumo real mensual'}
                              </Badge>
                            ) : device.energy_entity_id ? (
                              <Badge tone="yellow">HA sin lectura</Badge>
                            ) : device.entity_id ? (
                              <Badge tone="neutral">Entidad HA</Badge>
                            ) : null}
                          </div>
                        </div>
                      </div>
                      <div className="flex gap-8" style={{ flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                        <Button size="sm" variant="ghost" onClick={() => setHourlyDevice(device)}>
                          <BarChart3 size={14} /> Consumo
                        </Button>
                        <Button size="sm" variant="ghost" onClick={() => openEdit(device)}>
                          Editar <ChevronRight size={14} />
                        </Button>
                      </div>
                    </div>

                    <div className="between mt-16" style={{ alignItems: 'flex-end' }}>
                      <div>
                        <div className="big-number" style={{ fontSize: 28 }}>
                          {eur(device.cost)}
                        </div>
                        <div className="small muted">coste energía estimado / mes</div>
                      </div>
                      <div className="right">
                        <div className="device-cost">{kwh(device.energy_kwh)}</div>
                        <div className="device-kwh">
                          {pct(device.share, 0)} del total · {watts(device.power_active_w)}
                        </div>
                      </div>
                    </div>

                    <div className="mt-12">
                      <PeriodBar values={device.by_period} height={7} />
                      <div className="between mt-8">
                        <span className="small muted">Valle, llano y punta</span>
                        <span className="small muted">
                          {device.min_cost !== device.max_cost
                            ? `Rango ${eur(device.min_cost)}–${eur(device.max_cost)}`
                            : 'Consumo continuo'}
                        </span>
                      </div>
                    </div>

                    {device.notes_estimate.length > 0 ? (
                      <div className="small muted mt-8">{device.notes_estimate[0]}</div>
                    ) : null}
                  </div>
                </Card>
              ))}
            </div>
          )}

          <div className="banner mt-16">
            <Sparkles size={15} style={{ flexShrink: 0, marginTop: 1 }} />
            <span>
              Consejo: si no conoces la potencia exacta, usa la etiqueta energética o un medidor de enchufe.
              La calibración con la factura corrige el total aunque algún dato sea aproximado.
            </span>
          </div>
        </>
      )}

      <DeviceForm
        open={formOpen}
        device={editing}
        catalog={catalog}
        initialCategory={initialCategory}
        onClose={() => setFormOpen(false)}
        onSaved={async () => {
          await reload()
        }}
      />

      {hourlyDevice ? (
        <DeviceHourlyModal device={hourlyDevice} onClose={() => setHourlyDevice(null)} />
      ) : null}
    </div>
  )
}
