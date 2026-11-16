import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ArrowRight,
  Clock3,
  Github,
  Info,
  Plug,
  Radio,
  Repeat2,
  Trash2,
  Wand2,
} from 'lucide-react'
import { api } from '../api'
import { EntityPicker } from '../components/EntityPicker'
import { DeviceIcon } from '../components/Icon'
import {
  Badge,
  Button,
  Field,
  Input,
  Modal,
  Segmented,
  Select,
  Textarea,
  Toggle,
  useToast,
} from '../components/ui'
import {
  confidenceLabel,
  eur,
  kwh,
  modeLabel,
  pct,
  watts,
} from '../lib/format'
import type { CatalogItem, Device, DeviceInput, DeviceMode, DevicePreview, HaEntity, Window } from '../types'

function fromDevice(device: Device): DeviceInput {
  return {
    name: device.name,
    category: device.category,
    icon: device.icon,
    area: device.area,
    mode: device.mode,
    power_active_w: device.power_active_w,
    power_standby_w: device.power_standby_w,
    duty_cycle_pct: device.duty_cycle_pct,
    annual_kwh: device.annual_kwh,
    hours_per_day: device.hours_per_day,
    cycles_per_week: device.cycles_per_week,
    minutes_per_cycle: device.minutes_per_cycle,
    energy_per_cycle_kwh: device.energy_per_cycle_kwh,
    always_plugged: device.always_plugged,
    typical_windows: device.typical_windows,
    flexibility: device.flexibility,
    entity_id: device.entity_id,
    energy_entity_id: device.energy_entity_id,
    enabled: device.enabled,
    notes: device.notes,
  }
}

function fromCatalog(item: CatalogItem, current?: DeviceInput): DeviceInput {
  return {
    name: current?.name && current.name !== 'Nuevo dispositivo' ? current.name : item.name,
    category: item.id,
    icon: item.icon,
    area: current?.area ?? '',
    mode: item.mode,
    power_active_w: item.power_active_w,
    power_standby_w: item.power_standby_w,
    duty_cycle_pct: item.duty_cycle_pct,
    annual_kwh: item.annual_kwh,
    hours_per_day: item.hours_per_day,
    cycles_per_week: item.cycles_per_week,
    minutes_per_cycle: item.minutes_per_cycle,
    energy_per_cycle_kwh: item.energy_per_cycle_kwh,
    always_plugged: item.always_plugged,
    typical_windows: null,
    flexibility: item.flexibility,
    entity_id: null,
    energy_entity_id: null,
    enabled: true,
    notes: null,
  }
}

const EMPTY: DeviceInput = {
  name: 'Nuevo dispositivo',
  category: 'other',
  icon: 'plug',
  area: '',
  mode: 'hours_per_day',
  power_active_w: 100,
  power_standby_w: 0,
  duty_cycle_pct: 100,
  annual_kwh: null,
  hours_per_day: 1,
  cycles_per_week: 0,
  minutes_per_cycle: 0,
  energy_per_cycle_kwh: null,
  always_plugged: true,
  typical_windows: null,
  flexibility: 'none',
  entity_id: null,
  energy_entity_id: null,
  enabled: true,
  notes: null,
}

export function DeviceForm({
  open,
  device,
  catalog,
  initialCategory,
  onClose,
  onSaved,
}: {
  open: boolean
  device: Device | null
  catalog: CatalogItem[]
  initialCategory?: string | null
  onClose: () => void
  onSaved: () => Promise<void>
}) {
  const { showToast } = useToast()
  const navigate = useNavigate()
  const [form, setForm] = useState<DeviceInput>(EMPTY)
  const [preview, setPreview] = useState<DevicePreview | null>(null)
  const [previewError, setPreviewError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [entities, setEntities] = useState<HaEntity[]>([])
  const [energyEntities, setEnergyEntities] = useState<HaEntity[]>([])
  const [entitiesConfigured, setEntitiesConfigured] = useState(false)

  const selectedCatalog = useMemo(
    () => catalog.find((item) => item.id === form.category) ?? catalog.find((item) => item.id === 'other'),
    [catalog, form.category],
  )
  const annualKwh = Number(form.annual_kwh ?? 0)
  const annualOnly = form.mode === 'always_on' && annualKwh > 0
  const averageAnnualW = annualKwh > 0 ? (annualKwh * 1000) / 8760 : 0
  const selectedEnergyEntity = energyEntities.find(
    (entity) => entity.entity_id === form.energy_entity_id,
  )

  useEffect(() => {
    if (!open) return
    setError(null)
    setPreview(null)
    setPreviewError(null)
    if (device) {
      setForm(fromDevice(device))
    } else {
      const item = initialCategory ? catalog.find((entry) => entry.id === initialCategory) : undefined
      setForm(item ? fromCatalog(item) : EMPTY)
    }
  }, [open, device, initialCategory, catalog])

  useEffect(() => {
    if (!open || form.mode !== 'entity') return
    let cancelled = false
    Promise.allSettled([api.haEntities('control'), api.haEntities('energy')]).then((results) => {
      if (cancelled) return
      const [controlResult, energyResult] = results
      const control =
        controlResult.status === 'fulfilled'
          ? controlResult.value
          : { configured: false, items: [] }
      const energy =
        energyResult.status === 'fulfilled'
          ? energyResult.value
          : { configured: false, items: [] }
      setEntities(control.items)
      setEnergyEntities(energy.items)
      setEntitiesConfigured(Boolean(control.configured || energy.configured))
    })
    return () => {
      cancelled = true
    }
  }, [open, form.mode])

  useEffect(() => {
    if (!open) return
    const timer = window.setTimeout(() => {
      api
        .previewDevice(form)
        .then((result) => {
          setPreview(result)
          setPreviewError(null)
        })
        .catch((err) => {
          setPreview(null)
          setPreviewError(err instanceof Error ? err.message : 'No se ha podido calcular la vista previa')
        })
    }, 420)
    return () => window.clearTimeout(timer)
  }, [open, form])

  const update = <K extends keyof DeviceInput>(key: K, value: DeviceInput[K]) => {
    setForm((current) => ({ ...current, [key]: value }))
  }

  const chooseCategory = (categoryId: string) => {
    const item = catalog.find((entry) => entry.id === categoryId)
    if (!item) return
    setForm((current) => {
      const previousName = catalog.find((entry) => entry.id === current.category)?.name
      const shouldReplaceName =
        !current.name ||
        current.name === 'Nuevo dispositivo' ||
        current.name === previousName
      const next = fromCatalog(item, current)
      next.name = shouldReplaceName ? item.name : current.name
      return next
    })
  }

  const chooseMode = (mode: DeviceMode) => {
    update('mode', mode)
    if (mode === 'always_on') {
      setForm((current) => ({ ...current, always_plugged: true }))
    }
  }

  const save = async () => {
    setError(null)
    if (!form.name.trim()) {
      setError('Ponle un nombre al dispositivo.')
      return
    }
    setSaving(true)
    try {
      if (device) {
        await api.updateDevice(device.id, form)
        showToast('Dispositivo actualizado')
      } else {
        await api.createDevice(form)
        showToast('Dispositivo añadido')
      }
      await onSaved()
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se ha podido guardar el dispositivo')
    } finally {
      setSaving(false)
    }
  }

  const remove = async () => {
    if (!device) return
    if (!window.confirm(`¿Eliminar ${device.name}? Los cálculos dejarán de incluirlo.`)) return
    setDeleting(true)
    setError(null)
    try {
      await api.deleteDevice(device.id)
      showToast('Dispositivo eliminado')
      await onSaved()
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se ha podido eliminar el dispositivo')
    } finally {
      setDeleting(false)
    }
  }

  const typicalWindows: Window[] = (form.typical_windows as Window[] | null | undefined) ?? selectedCatalog?.typical_windows ?? []
  const confidenceTone = preview?.confidence === 'alta' ? 'green' : preview?.confidence === 'media' ? 'yellow' : 'red'
  const previewHasPrice = preview?.price_available !== false

  return (
    <Modal
      open={open}
      onClose={onClose}
      size="lg"
      title={device ? `Editar ${device.name}` : 'Añadir dispositivo'}
      subtitle="No necesitas sensores: define cuánto consume y cómo lo usas."
      footer={
        <>
          {device ? (
            <Button variant="danger" onClick={() => void remove()} disabled={deleting || saving} style={{ marginRight: 'auto' }}>
              <Trash2 size={14} /> {deleting ? 'Eliminando…' : 'Eliminar'}
            </Button>
          ) : null}
          <Button onClick={onClose} disabled={saving}>
            Cancelar
          </Button>
          <Button variant="primary" onClick={() => void save()} disabled={saving}>
            {saving ? 'Guardando…' : device ? 'Guardar cambios' : 'Añadir dispositivo'}
          </Button>
        </>
      }
    >
      {error ? <div className="error-box mb-12">{error}</div> : null}
      <div className="form-grid" style={{ alignItems: 'start' }}>
        <div style={{ display: 'grid', gap: 14 }}>
          <div className="form-grid">
            <Field label="Nombre">
              <Input
                value={form.name}
                onChange={(event) => update('name', event.target.value)}
                placeholder="Nevera, lavadora, TV…"
              />
            </Field>
            <Field label="Zona" hint="Opcional: cocina, salón, lavadero…">
              <Input
                value={form.area ?? ''}
                onChange={(event) => update('area', event.target.value)}
                placeholder="Cocina"
              />
            </Field>
          </div>

          <Field label="Tipo de aparato" hint={selectedCatalog?.description}>
            <Select value={form.category} onChange={(event) => chooseCategory(event.target.value)}>
              {catalog.map((item) => (
                <option value={item.id} key={item.id}>
                  {item.name}
                </option>
              ))}
            </Select>
          </Field>

          <Field label="¿Cómo lo calculamos?">
            <Segmented
              value={form.mode}
              onChange={chooseMode}
              options={[
                { value: 'always_on', label: 'Siempre enchufado', icon: <Plug size={13} /> },
                { value: 'hours_per_day', label: 'Horas al día', icon: <Clock3 size={13} /> },
                { value: 'cycles', label: 'Por ciclos', icon: <Repeat2 size={13} /> },
                { value: 'entity', label: 'Entidad de HA', icon: <Radio size={13} /> },
              ]}
            />
          </Field>

          {form.mode === 'always_on' ? (
            <>
              <div className="banner">
                <Plug size={14} style={{ flexShrink: 0, marginTop: 1 }} />
                <span>
                  Para nevera, router o standby. Si conoces el <strong>consumo anual</strong> de la
                  etiqueta, es el único dato necesario. Si no, usa potencia y ciclo de trabajo.
                </span>
              </div>
              <Field
                label="Consumo anual (kWh)"
                hint="Etiqueta energética. Si lo rellenas, no necesitas potencia ni ciclo de trabajo."
              >
                <Input
                  type="number"
                  min="0"
                  step="1"
                  value={form.annual_kwh ?? ''}
                  placeholder="Ej. 257"
                  onChange={(event) =>
                    update('annual_kwh', event.target.value === '' ? null : Number(event.target.value))
                  }
                />
              </Field>
              {annualOnly ? (
                <div className="annual-summary">
                  <div className="between" style={{ alignItems: 'flex-start', gap: 12 }}>
                    <div>
                      <div className="eyebrow" style={{ marginBottom: 2 }}>
                        <Wand2 size={11} /> Cálculo por etiqueta
                      </div>
                      <div className="small muted">
                        Repartimos el consumo anual entre las 24 h del día.
                      </div>
                    </div>
                    <Badge tone="green">{kwh(annualKwh, 0)}/año</Badge>
                  </div>
                  <div className="annual-summary-grid">
                    <div className="annual-summary-metric">
                      <span className="small muted">Media diaria</span>
                      <strong>{kwh(annualKwh / 365, 2)}</strong>
                    </div>
                    <div className="annual-summary-metric">
                      <span className="small muted">Potencia media</span>
                      <strong>{watts(averageAnnualW)}</strong>
                    </div>
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => update('annual_kwh', null)}
                  >
                    Calcular con potencia y ciclo <ArrowRight size={13} />
                  </Button>
                </div>
              ) : (
                <div className="form-grid">
                  <Field label="Potencia activa (W)" hint={`${watts(form.power_active_w)} cuando funciona`}>
                    <Input
                      type="number"
                      min="0"
                      step="1"
                      value={form.power_active_w}
                      onChange={(event) => update('power_active_w', Number(event.target.value))}
                    />
                  </Field>
                  <Field label="Ciclo de trabajo (%)" hint="Nevera: 30–40 %. Router: 100 %.">
                    <Input
                      type="number"
                      min="0"
                      max="100"
                      step="1"
                      value={form.duty_cycle_pct}
                      onChange={(event) => update('duty_cycle_pct', Number(event.target.value))}
                    />
                  </Field>
                  <Field label="Standby (W)" hint="Consumo cuando el aparato está en reposo.">
                    <Input
                      type="number"
                      min="0"
                      step="0.1"
                      value={form.power_standby_w}
                      onChange={(event) => update('power_standby_w', Number(event.target.value))}
                    />
                  </Field>
                </div>
              )}
            </>
          ) : null}

          {form.mode === 'hours_per_day' ? (
            <>
              <div className="form-grid">
                <Field label="Potencia activa (W)" hint={`${watts(form.power_active_w)} mientras está encendido`}>
                  <Input
                    type="number"
                    min="0"
                    step="1"
                    value={form.power_active_w}
                    onChange={(event) => update('power_active_w', Number(event.target.value))}
                  />
                </Field>
                <Field label="Horas al día" hint="Media diaria. No hace falta indicar la franja.">
                  <Input
                    type="number"
                    min="0"
                    max="24"
                    step="0.1"
                    value={form.hours_per_day}
                    onChange={(event) => update('hours_per_day', Number(event.target.value))}
                  />
                </Field>
                <Field label="Standby (W)" hint="0 si no queda enchufado o no consume en reposo.">
                  <Input
                    type="number"
                    min="0"
                    step="0.1"
                    value={form.power_standby_w}
                    onChange={(event) => update('power_standby_w', Number(event.target.value))}
                  />
                </Field>
                <Field label="Flexibilidad" hint="Para recomendar el mejor horario.">
                  <Select
                    value={form.flexibility}
                    onChange={(event) => update('flexibility', event.target.value as DeviceInput['flexibility'])}
                  >
                    <option value="flexible">Flexible: puedo moverlo a valle</option>
                    <option value="semi">Semi-flexible: a veces</option>
                    <option value="none">No flexible: uso a esa hora</option>
                  </Select>
                </Field>
              </div>
              <Toggle
                checked={form.always_plugged}
                onChange={(value) => update('always_plugged', value)}
                label="Está siempre enchufado"
                hint="Si lo está, añadimos el standby de las horas en que no se usa."
              />
            </>
          ) : null}

          {form.mode === 'cycles' ? (
            <>
              <div className="form-grid">
                <Field label="Ciclos por semana" hint="Lavadora: 3–5. Lavavajillas: 5–7.">
                  <Input
                    type="number"
                    min="0"
                    step="0.5"
                    value={form.cycles_per_week}
                    onChange={(event) => update('cycles_per_week', Number(event.target.value))}
                  />
                </Field>
                <Field label="Duración del ciclo (min)">
                  <Input
                    type="number"
                    min="0"
                    step="5"
                    value={form.minutes_per_cycle}
                    onChange={(event) => update('minutes_per_cycle', Number(event.target.value))}
                  />
                </Field>
                <Field label="kWh por ciclo" hint="Opcional. Si no lo sabes, se calcula con W × minutos.">
                  <Input
                    type="number"
                    min="0"
                    step="0.01"
                    value={form.energy_per_cycle_kwh ?? ''}
                    placeholder="Ej. 0.9"
                    onChange={(event) =>
                      update('energy_per_cycle_kwh', event.target.value === '' ? null : Number(event.target.value))
                    }
                  />
                </Field>
                <Field label="Potencia activa (W)" hint="Solo se usa si no indicas kWh por ciclo.">
                  <Input
                    type="number"
                    min="0"
                    step="1"
                    value={form.power_active_w}
                    onChange={(event) => update('power_active_w', Number(event.target.value))}
                  />
                </Field>
                <Field label="Standby (W)">
                  <Input
                    type="number"
                    min="0"
                    step="0.1"
                    value={form.power_standby_w}
                    onChange={(event) => update('power_standby_w', Number(event.target.value))}
                  />
                </Field>
                <Field label="Flexibilidad">
                  <Select
                    value={form.flexibility}
                    onChange={(event) => update('flexibility', event.target.value as DeviceInput['flexibility'])}
                  >
                    <option value="flexible">Flexible: puedo moverlo a valle</option>
                    <option value="semi">Semi-flexible: a veces</option>
                    <option value="none">No flexible: uso a esa hora</option>
                  </Select>
                </Field>
              </div>
              <Toggle
                checked={form.always_plugged}
                onChange={(value) => update('always_plugged', value)}
                label="Está siempre enchufado"
                hint="Añade el standby de las horas sin ciclo."
              />
            </>
          ) : null}

          {form.mode === 'entity' ? (
            <>
              {!entitiesConfigured ? (
                <div className="banner warning">
                  Home Assistant no está conectado. Puedes guardar la entidad cuando lo esté; mientras
                  tanto, usa una estimación por horas.
                </div>
              ) : null}
              <div className="banner accent">
                <Info size={14} style={{ flexShrink: 0, marginTop: 1 }} />
                <span>
                  La <strong>entidad de energía</strong> debe ser un contador acumulado en kWh o Wh.
                  Si la eliges, el consumo del mes sale de Home Assistant. La entidad de estado es
                  opcional y queda guardada como referencia; el reparto por horas usa la franja típica.
                </span>
              </div>
              <Field
                label="Entidad de energía (kWh)"
                hint="Opcional. Si la eliges, usamos el consumo real del mes."
              >
                <EntityPicker
                  entities={energyEntities}
                  value={form.energy_entity_id ?? ''}
                  onChange={(value) => update('energy_entity_id', value || null)}
                  emptyLabel="Sin entidad de energía"
                  placeholder="Buscar sensor de energía…"
                  hint={
                    selectedEnergyEntity
                      ? `${selectedEnergyEntity.state} ${selectedEnergyEntity.unit ?? ''} · ${
                          selectedEnergyEntity.state_class ?? 'sin state_class'
                        }`
                      : undefined
                  }
                />
                {entitiesConfigured && energyEntities.length === 0 ? (
                  <div className="field-hint">
                    No hay sensores de energía compatibles expuestos en Home Assistant.
                  </div>
                ) : null}
              </Field>
              {selectedEnergyEntity?.state_class === 'measurement' ? (
                <div className="banner warning">
                  <Info size={14} style={{ flexShrink: 0, marginTop: 1 }} />
                  <span>
                    Esa entidad parece una medición instantánea, no un contador acumulado. No se usará
                    para el consumo mensual; elige una entidad con estado <code>total_increasing</code>.
                  </span>
                </div>
              ) : null}
              <Field
                label="Entidad de estado (opcional)"
                hint="Se guarda como referencia. El reparto actual usa la franja típica."
              >
                <EntityPicker
                  entities={entities}
                  value={form.entity_id ?? ''}
                  onChange={(value) => update('entity_id', value || null)}
                  emptyLabel="Sin entidad de estado"
                  placeholder="Buscar por nombre o entity_id…"
                  hint="Entidades de control de Home Assistant"
                />
              </Field>
              <div className="form-grid">
                <Field label="Potencia activa (W)">
                  <Input
                    type="number"
                    min="0"
                    step="1"
                    value={form.power_active_w}
                    onChange={(event) => update('power_active_w', Number(event.target.value))}
                  />
                </Field>
                <Field label="Horas al día de respaldo" hint="Se usa si aún no hay historial.">
                  <Input
                    type="number"
                    min="0"
                    max="24"
                    step="0.1"
                    value={form.hours_per_day}
                    onChange={(event) => update('hours_per_day', Number(event.target.value))}
                  />
                </Field>
                <Field label="Standby (W)">
                  <Input
                    type="number"
                    min="0"
                    step="0.1"
                    value={form.power_standby_w}
                    onChange={(event) => update('power_standby_w', Number(event.target.value))}
                  />
                </Field>
                <Field label="Flexibilidad">
                  <Select
                    value={form.flexibility}
                    onChange={(event) => update('flexibility', event.target.value as DeviceInput['flexibility'])}
                  >
                    <option value="flexible">Flexible</option>
                    <option value="semi">Semi-flexible</option>
                    <option value="none">No flexible</option>
                  </Select>
                </Field>
              </div>
            </>
          ) : null}

          <Field label="Notas" hint="Opcional: modelo, etiqueta energética, dónde está…">
            <Textarea
              value={form.notes ?? ''}
              onChange={(event) => update('notes', event.target.value)}
              placeholder="Ej. Frigorífico combi de 200 kWh/año en la cocina"
            />
          </Field>
        </div>

        <div
          style={{
            position: 'sticky',
            top: 0,
            display: 'grid',
            gap: 12,
            padding: 16,
            border: '1px solid var(--border)',
            borderRadius: 15,
            background: 'var(--bg-soft)',
          }}
        >
          <div className="between">
            <div>
              <div className="eyebrow" style={{ marginBottom: 2 }}>
                <Wand2 size={11} /> Vista previa
              </div>
              <div className="small muted">
                {form.mode === 'entity'
                  ? form.energy_entity_id
                    ? 'Consumo desde Home Assistant'
                    : 'Estimación de respaldo con horas al día'
                  : `Estimación de ${modeLabel(form.mode).toLowerCase()}`}
              </div>
            </div>
            <div className="device-icon">
              <DeviceIcon name={form.icon ?? selectedCatalog?.icon} size={21} />
            </div>
          </div>

          {preview ? (
            <>
              <div>
                <div className="big-number">{kwh(preview.energy_kwh)}</div>
                <div className="small muted">al mes</div>
              </div>
              <div className="between">
                <span className="small muted">Coste energía</span>
                <strong>{previewHasPrice ? eur(preview.cost_eur) : '—'}</strong>
              </div>
              {preview.energy_source === 'ha_energy_sensor' ? (
                <Badge tone="green">Consumo real desde Home Assistant</Badge>
              ) : form.mode === 'entity' && preview.energy_entity_id ? (
                <div className="banner warning">
                  <Info size={14} style={{ flexShrink: 0, marginTop: 1 }} />
                  <span>
                    No se ha podido usar la entidad de energía
                    {preview.energy_error ? `: ${preview.energy_error}` : '.'} Se usará la estimación
                    manual como respaldo.
                  </span>
                </div>
              ) : null}
              {!previewHasPrice ? (
                <>
                  <div className="banner warning">
                    <Info size={14} style={{ flexShrink: 0, marginTop: 1 }} />
                    <span>
                      <strong>Sin precio confirmado.</strong> No hay tarifa válida para{' '}
                      {preview.price_month_label ?? 'este mes'}. El consumo se calcula, pero el coste
                      aparecerá cuando confirmes los precios.
                    </span>
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="w-full"
                    onClick={() => {
                      onClose()
                      navigate('/tariff')
                    }}
                  >
                    Ir a Tarifa <ArrowRight size={13} />
                  </Button>
                </>
              ) : preview.price_is_fallback ? (
                <div className="small muted">
                  Coste con precios provisionales. Confirma la tarifa para ajustarlo.
                </div>
              ) : null}
              {preview.energy_kwh > 0 ? (
                <div>
                  <div className="between small" style={{ marginBottom: 6 }}>
                    <span className="muted">Reparto por tramo</span>
                    <Badge tone={confidenceTone}>{confidenceLabel(preview.confidence)}</Badge>
                  </div>
                  <div style={{ display: 'flex', height: 10, borderRadius: 99, overflow: 'hidden' }}>
                    {(['P1', 'P2', 'P3'] as const).map((period) => {
                      const total = preview.periods.reduce((sum, item) => sum + item.energy_kwh, 0) || 1
                      const item = preview.periods.find((entry) => entry.id === period)
                      return (
                        <span
                          key={period}
                          style={{
                            width: `${((item?.energy_kwh ?? 0) / total) * 100}%`,
                            background:
                              period === 'P1' ? 'var(--p1)' : period === 'P2' ? 'var(--p2)' : 'var(--p3)',
                          }}
                        />
                      )
                    })}
                  </div>
                  <div className="small muted mt-8">
                    {preview.periods
                      .map((item) => `${item.name} ${kwh(item.energy_kwh, 0)}`)
                      .join(' · ')}
                  </div>
                </div>
              ) : null}
              {preview.min_cost_eur !== preview.max_cost_eur ? (
                <div className="small muted">
                  Rango según cuándo lo uses: {eur(preview.min_cost_eur)} – {eur(preview.max_cost_eur)}.
                </div>
              ) : null}
              {typicalWindows.length > 0 && form.mode !== 'always_on' ? (
                <div className="small muted">
                  Franja típica: {typicalWindows.map((window) => `${window.start}–${window.end}`).join(', ')}.
                  Puedes cambiarla después.
                </div>
              ) : null}
              {preview.notes.slice(0, 2).map((note) => (
                <div className="small muted" key={note}>
                  · {note}
                </div>
              ))}
            </>
          ) : previewError ? (
            <div className="small" style={{ color: 'var(--danger)' }}>
              {previewError}
            </div>
          ) : (
            <div className="small muted">Completa los datos para ver la estimación.</div>
          )}

          {!preview && !previewError ? <div className="spinner" style={{ width: 18, height: 18 }} /> : null}

          <div className="small muted" style={{ borderTop: '1px solid var(--border)', paddingTop: 10 }}>
            {annualOnly
              ? 'Repartimos el consumo anual de la etiqueta entre las 24 h y aplicamos el precio de cada tramo.'
              : form.mode === 'always_on'
                ? 'Repartimos el consumo entre las 24 h y aplicamos el precio de cada tramo.'
                : 'Repartimos las horas según la franja típica de la categoría. El rango muestra el mínimo en valle y el máximo en punta.'}
          </div>
        </div>
      </div>
    </Modal>
  )
}
