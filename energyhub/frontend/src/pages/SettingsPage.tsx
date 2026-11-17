import { useEffect, useState } from 'react'
import {
  BookOpen,
  CheckCircle2,
  Database,
  Download,
  ExternalLink,
  Github,
  HardDrive,
  Info,
  Link2,
  Moon,
  RefreshCw,
  Server,
  Settings2,
  Sparkles,
  Sun,
  Trash2,
  Wifi,
  WifiOff,
} from 'lucide-react'
import { api } from '../api'
import { EntityPicker } from '../components/EntityPicker'
import {
  Badge,
  Banner,
  Button,
  Card,
  ErrorBox,
  Field,
  Input,
  Loading,
  useToast,
} from '../components/ui'
import { useApi } from '../hooks/useApi'
import type { Bootstrap, HaEntity, HaStatus } from '../types'

interface Settings {
  esios_entity_id: string
  language: string
  theme: string
  demo_mode: boolean
  shift_flexible_pct: number
  shift_semi_pct: number
}

type Theme = 'dark' | 'light'

function applyTheme(theme: Theme) {
  document.documentElement.dataset.theme = theme
  localStorage.setItem('energyhub-theme', theme)
}

export function SettingsPage({ onChanged }: { onChanged: () => Promise<void> }) {
  const { showToast } = useToast()
  const { data: bootstrap, reload: reloadBootstrap } = useApi<Bootstrap>('/bootstrap')
  const { data: haStatus, reload: reloadHa } = useApi<HaStatus>('/ha/status')
  const { data: settings, reload: reloadSettings } = useApi<Settings>('/settings')
  const { data: priceEntities } = useApi<{ configured: boolean; items: HaEntity[] }>('/ha/entities?kind=price')
  const [esiosEntity, setEsiosEntity] = useState('')
  const [savingEsios, setSavingEsios] = useState(false)
  const [shiftFlexible, setShiftFlexible] = useState('70')
  const [shiftSemi, setShiftSemi] = useState('30')
  const [savingShift, setSavingShift] = useState(false)
  const [busy, setBusy] = useState<'demo' | 'reset' | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [theme, setTheme] = useState<Theme>(() =>
    document.documentElement.dataset.theme === 'light' ? 'light' : 'dark',
  )

  useEffect(() => {
    if (settings?.esios_entity_id) setEsiosEntity(settings.esios_entity_id)
  }, [settings?.esios_entity_id])

  useEffect(() => {
    if (!settings) return
    setShiftFlexible(String(settings.shift_flexible_pct ?? 70))
    setShiftSemi(String(settings.shift_semi_pct ?? 30))
  }, [settings])

  const saveShift = async () => {
    setSavingShift(true)
    setError(null)
    try {
      await api.updateSettings({
        shift_flexible_pct: Number(shiftFlexible),
        shift_semi_pct: Number(shiftSemi),
      })
      showToast('Cálculo del ahorro actualizado')
      await reloadSettings()
      await onChanged()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se han podido guardar los porcentajes')
    } finally {
      setSavingShift(false)
    }
  }

  const saveEsios = async () => {
    setSavingEsios(true)
    setError(null)
    try {
      await api.updateSettings({ esios_entity_id: esiosEntity || null })
      showToast('Sensor ESIOS actualizado')
      await reloadSettings()
      await onChanged()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se ha podido guardar el sensor')
    } finally {
      setSavingEsios(false)
    }
  }

  const loadDemo = async () => {
    setBusy('demo')
    setError(null)
    try {
      await api.seedDemo()
      showToast('Datos de ejemplo cargados')
      await onChanged()
      await reloadBootstrap()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se ha podido cargar la demo')
    } finally {
      setBusy(null)
    }
  }

  const reset = async () => {
    if (!window.confirm('Se borrarán el contrato, los dispositivos y las calibraciones. ¿Continuar?')) return
    setBusy('reset')
    setError(null)
    try {
      await api.resetDemo()
      showToast('Datos eliminados')
      await onChanged()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se han podido borrar los datos')
    } finally {
      setBusy(null)
    }
  }

  const changeTheme = (value: Theme) => {
    setTheme(value)
    applyTheme(value)
  }

  if (!bootstrap) return <Loading label="Cargando ajustes…" />

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <div className="eyebrow">
            <Settings2 size={12} /> Ajustes
          </div>
          <h1 className="page-title">Control y transparencia.</h1>
          <p className="page-subtitle">
            Conexión con Home Assistant, sensor de mercado, datos y apariencia. EnergyHub funciona sin
            enviar información a terceros.
          </p>
        </div>
        <div className="actions">
          <Button onClick={() => void reloadBootstrap()}>
            <RefreshCw size={14} /> Actualizar estado
          </Button>
        </div>
      </div>

      {error ? <ErrorBox message={error} /> : null}

      <div className="card-grid mt-16">
        <Card className="span-7">
          <div className="card-header">
            <div>
              <h2 className="card-title">Home Assistant</h2>
              <p className="card-subtitle">La app se instala como add-on y usa el token del Supervisor.</p>
            </div>
            {haStatus?.connected ? (
              <Badge tone="green">
                <Wifi size={12} /> Conectado
              </Badge>
            ) : (
              <Badge tone="neutral">
                <WifiOff size={12} /> Sin conexión
              </Badge>
            )}
          </div>
          <div className="card-body">
            {haStatus?.configured ? (
              <>
                <div className="form-grid">
                  <div>
                    <div className="field-label">Versión</div>
                    <div>{haStatus.version ?? '—'}</div>
                  </div>
                  <div>
                    <div className="field-label">Instalación</div>
                    <div>{haStatus.location_name ?? '—'}</div>
                  </div>
                  <div>
                    <div className="field-label">Zona horaria</div>
                    <div>{haStatus.timezone ?? '—'}</div>
                  </div>
                  <div>
                    <div className="field-label">Estado</div>
                    <div>{haStatus.connected ? 'Conectado' : 'No disponible'}</div>
                  </div>
                </div>
                {haStatus.error ? <div className="error-box mt-12">{haStatus.error}</div> : null}
                <div className="between mt-16">
                  <span className="small muted">
                    Los datos de dispositivos y entidades se leen directamente de HA.
                  </span>
                  <Button size="sm" onClick={() => void reloadHa()}>
                    <RefreshCw size={13} /> Probar conexión
                  </Button>
                </div>
              </>
            ) : (
              <div className="banner">
                <Server size={15} style={{ flexShrink: 0, marginTop: 1 }} />
                <span>
                  No se ha detectado Home Assistant. Si estás ejecutando la app fuera de HA, define
                  <code> HA_URL </code> y <code> HA_TOKEN </code> en el entorno del backend. Dentro de HA,
                  funciona automáticamente con Ingress.
                </span>
              </div>
            )}
          </div>
        </Card>

        <Card className="span-5">
          <div className="card-header">
            <div>
              <h2 className="card-title">Apariencia</h2>
              <p className="card-subtitle">El panel respeta tu preferencia.</p>
            </div>
            <Sun size={17} className="muted" />
          </div>
          <div className="card-body">
            <div className="segmented" style={{ gridTemplateColumns: '1fr 1fr' }}>
              <button
                type="button"
                className={`segment ${theme === 'dark' ? 'active' : ''}`}
                onClick={() => changeTheme('dark')}
              >
                <Moon size={14} /> Oscuro
              </button>
              <button
                type="button"
                className={`segment ${theme === 'light' ? 'active' : ''}`}
                onClick={() => changeTheme('light')}
              >
                <Sun size={14} /> Claro
              </button>
            </div>
            <div className="small muted mt-12">
              El tema se guarda en este navegador. Home Assistant puede seguir usando su propio tema.
            </div>
            <div className="divider" style={{ height: 1, background: 'var(--border)', margin: '16px 0' }} />
            <div className="between">
              <span className="small muted">Idioma</span>
              <Badge tone="neutral">Español</Badge>
            </div>
            <div className="small muted mt-8">
              La arquitectura está preparada para añadir inglés y otros idiomas.
            </div>
          </div>
        </Card>

        <Card className="span-12">
          <div className="card-header">
            <div>
              <h2 className="card-title">Cálculo del ahorro potencial</h2>
              <p className="card-subtitle">
                Qué parte del consumo en punta/llano se supone que puedes mover a valle.
              </p>
            </div>
            <Sparkles size={17} className="muted" />
          </div>
          <div className="card-body">
            <div className="form-grid">
              <Field
                label="Aparatos flexibles (%)"
                hint="70 % es conservador. 100 % supone que todo su consumo de punta/llano puede pasar a valle."
              >
                <Input
                  type="number"
                  min="0"
                  max="100"
                  step="5"
                  value={shiftFlexible}
                  onChange={(event) => setShiftFlexible(event.target.value)}
                />
              </Field>
              <Field
                label="Semi-flexibles (%)"
                hint="Porcentaje que se supone movible en los aparatos marcados como semi-flexibles."
              >
                <Input
                  type="number"
                  min="0"
                  max="100"
                  step="5"
                  value={shiftSemi}
                  onChange={(event) => setShiftSemi(event.target.value)}
                />
              </Field>
            </div>
            <div className="between mt-12" style={{ gap: 12, flexWrap: 'wrap' }}>
              <span className="small muted">
                Se usa para el ahorro potencial y las recomendaciones. No cambia el consumo ni el coste
                real.
              </span>
              <Button onClick={() => void saveShift()} disabled={savingShift}>
                <CheckCircle2 size={14} /> {savingShift ? 'Guardando…' : 'Guardar porcentajes'}
              </Button>
            </div>
          </div>
        </Card>

        <Card className="span-7">
          <div className="card-header">
            <div>
              <h2 className="card-title">Sensor de mercado ESIOS</h2>
              <p className="card-subtitle">Opcional. Referencia de precio horario, no factura de Pepe.</p>
            </div>
            <Link2 size={17} className="muted" />
          </div>
          <div className="card-body">
            <Field
              label="Entidad de Home Assistant"
              hint="Selecciona el sensor de Conecta ESIOS o cualquier sensor de precio en €/kWh."
            >
              <EntityPicker
                entities={priceEntities?.items ?? []}
                value={esiosEntity}
                onChange={setEsiosEntity}
                emptyLabel="Sin sensor"
                placeholder="Buscar sensor de precio…"
                hint="Sensores en €/kWh"
              />
            </Field>
            {!priceEntities?.configured ? (
              <div className="small muted mt-8">Conecta Home Assistant para listar entidades.</div>
            ) : null}
            <div className="between mt-12">
              <span className="small muted">Solo se usa como referencia visual en el MVP.</span>
              <Button onClick={() => void saveEsios()} disabled={savingEsios}>
                <CheckCircle2 size={14} /> {savingEsios ? 'Guardando…' : 'Guardar sensor'}
              </Button>
            </div>
          </div>
        </Card>

        <Card className="span-5">
          <div className="card-header">
            <div>
              <h2 className="card-title">Datos</h2>
              <p className="card-subtitle">Todo local, dentro de Home Assistant.</p>
            </div>
            <Database size={17} className="muted" />
          </div>
          <div className="card-body">
            <div className="flex gap-8" style={{ flexWrap: 'wrap' }}>
              <a className="btn btn-secondary" href={api.exportUrl()} download>
                <Download size={14} /> Exportar JSON
              </a>
              <Button onClick={() => void loadDemo()} disabled={busy !== null}>
                <Sparkles size={14} /> {busy === 'demo' ? 'Cargando…' : 'Cargar demo'}
              </Button>
            </div>
            <div className="banner mt-12">
              <HardDrive size={14} style={{ flexShrink: 0, marginTop: 1 }} />
              <span>
                La base de datos SQLite vive en <code>/data/energyhub.db</code> y entra en las copias de
                seguridad de Home Assistant.
              </span>
            </div>
            <div className="divider" style={{ height: 1, background: 'var(--border)', margin: '16px 0' }} />
            <Button variant="danger" onClick={() => void reset()} disabled={busy !== null} className="w-full">
              <Trash2 size={14} /> {busy === 'reset' ? 'Borrando…' : 'Empezar de cero'}
            </Button>
            <div className="small muted mt-8">
              Elimina contrato, dispositivos, precios y calibraciones. No toca Home Assistant.
            </div>
          </div>
        </Card>

        <Card className="span-12">
          <div className="card-header">
            <div>
              <h2 className="card-title">Acerca de EnergyHub</h2>
              <p className="card-subtitle">Open source, local y hecho para entender la factura.</p>
            </div>
            <Badge tone="accent">v{bootstrap.app_version}</Badge>
          </div>
          <div className="card-body">
            <div className="card-grid">
              <div className="span-6">
                <div className="flex gap-8" style={{ alignItems: 'center' }}>
                  <BookOpen size={16} className="muted" />
                  <strong>Licencia MIT</strong>
                </div>
                <div className="small muted mt-8">
                  Puedes usarlo, modificarlo y compartirlo. Las estimaciones son orientativas y no
                  sustituyen a la factura de tu comercializadora.
                </div>
              </div>
              <div className="span-6">
                <div className="flex gap-8" style={{ alignItems: 'center' }}>
                  <Github size={16} className="muted" />
                  <strong>Proyecto</strong>
                </div>
                <div className="small muted mt-8">
                  EnergyHub nace para que cualquier persona pueda estimar su consumo sin depender de
                  sensores caros. La arquitectura está preparada para más países y tarifas.
                </div>
                <div className="flex gap-8 mt-12">
                  <a
                    className="btn btn-ghost btn-sm"
                    href="https://github.com/merchedev/EnergyHub"
                    target="_blank"
                    rel="noreferrer"
                  >
                    Repositorio <ExternalLink size={12} />
                  </a>
                  <span className="badge badge-neutral">
                    <Info size={11} /> v{bootstrap.app_version}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </Card>
      </div>
    </div>
  )
}


