import { useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  ArrowRight,
  Check,
  CheckCircle2,
  Code2,
  Copy,
  Lightbulb,
  RefreshCw,
  Sparkles,
  Trash2,
  Wand2,
  X,
} from 'lucide-react'
import { api } from '../api'
import {
  Badge,
  Banner,
  Button,
  Card,
  EmptyState,
  ErrorBox,
  Loading,
  Modal,
  Tabs,
  useClipboard,
  useToast,
} from '../components/ui'
import { useApi } from '../hooks/useApi'
import { confidenceLabel, eur, formatDateTime } from '../lib/format'
import type { Recommendation } from '../types'

type Filter = 'all' | 'savings' | 'warning' | 'info'

interface AutomationItem {
  id: number
  automation_id: string
  alias: string
  created_at: string
}

export function RecommendationsPage({ onCountChange }: { onCountChange?: (count: number) => void }) {
  const { showToast } = useToast()
  const copy = useClipboard()
  const { data, loading, error, reload } = useApi<{ items: Recommendation[] }>('/recommendations')
  const { data: automationsData, reload: reloadAutomations } = useApi<{ items: AutomationItem[] }>(
    '/automations',
  )
  const [filter, setFilter] = useState<Filter>('all')
  const [selected, setSelected] = useState<Recommendation | null>(null)
  const [creating, setCreating] = useState<string | null>(null)
  const [created, setCreated] = useState<Record<string, string>>({})
  const [dismissing, setDismissing] = useState<string | null>(null)

  const recommendations = data?.items ?? []

  useEffect(() => {
    onCountChange?.(recommendations.length)
  }, [recommendations.length, onCountChange])

  const filtered = useMemo(() => {
    if (filter === 'all') return recommendations
    if (filter === 'savings') return recommendations.filter((item) => item.savings_eur_month > 0)
    if (filter === 'warning') return recommendations.filter((item) => item.severity === 'high' || item.severity === 'warning')
    return recommendations.filter((item) => item.severity === 'info')
  }, [filter, recommendations])

  const savings = recommendations.reduce((sum, item) => sum + (item.savings_eur_month || 0), 0)
  const high = recommendations.filter((item) => item.severity === 'high').length

  const dismiss = async (id: string) => {
    setDismissing(id)
    try {
      await api.dismissRecommendation(id)
      showToast('Recomendación descartada')
      await reload()
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'No se ha podido descartar', 'error')
    } finally {
      setDismissing(null)
    }
  }

  const createAutomation = async (rec: Recommendation) => {
    setCreating(rec.id)
    try {
      const result = await api.createAutomation(rec.id)
      setCreated((current) => ({ ...current, [rec.id]: result.automation_id }))
      showToast('Automatización creada en Home Assistant')
      await reloadAutomations()
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'No se ha podido crear la automatización', 'error')
    } finally {
      setCreating(null)
    }
  }

  const undoAutomation = async (automationId: string, recId: string) => {
    if (!window.confirm('¿Deshacer esta automatización en Home Assistant?')) return
    try {
      await api.deleteAutomation(automationId)
      setCreated((current) => {
        const next = { ...current }
        delete next[recId]
        return next
      })
      showToast('Automatización eliminada')
      await reloadAutomations()
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'No se ha podido deshacer', 'error')
    }
  }

  if (loading && !data) return <Loading label="Analizando tu consumo…" />
  if (error && !data) return <ErrorBox message={error} />

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <div className="eyebrow">
            <Lightbulb size={12} /> Ahorro
          </div>
          <h1 className="page-title">Ideas que se notan en la factura.</h1>
          <p className="page-subtitle">
            Recomendaciones calculadas con tus aparatos, tu tarifa y tu consumo estimado. Sin promesas
            vacías: cada una muestra el ahorro y la confianza.
          </p>
        </div>
        <div className="actions">
          <Button onClick={() => void reload()}>
            <RefreshCw size={14} /> Reanalizar
          </Button>
        </div>
      </div>

      <div className="stat-grid">
        <div className="stat">
          <div className="stat-top">
            <span>Ahorro potencial</span>
            <Sparkles size={14} className="muted" />
          </div>
          <div className="stat-value" style={{ color: savings > 0 ? 'var(--success)' : undefined }}>
            {eur(savings)}
          </div>
          <div className="stat-meta">al mes, sumando acciones detectadas</div>
        </div>
        <div className="stat">
          <div className="stat-top">
            <span>Prioridad alta</span>
            <AlertTriangle size={14} className="muted" />
          </div>
          <div className="stat-value">{high}</div>
          <div className="stat-meta">acciones con más impacto</div>
        </div>
        <div className="stat">
          <div className="stat-top">
            <span>Recomendaciones</span>
            <Lightbulb size={14} className="muted" />
          </div>
          <div className="stat-value">{recommendations.length}</div>
          <div className="stat-meta">activas ahora mismo</div>
        </div>
        <div className="stat">
          <div className="stat-top">
            <span>Automatizaciones</span>
            <Wand2 size={14} className="muted" />
          </div>
          <div className="stat-value">{automationsData?.items.length ?? 0}</div>
          <div className="stat-meta">creadas por EnergyHub</div>
        </div>
      </div>

      <div className="between mt-16" style={{ flexWrap: 'wrap', gap: 12 }}>
        <Tabs
          value={filter}
          onChange={setFilter}
          options={[
            { value: 'all', label: `Todas (${recommendations.length})` },
            { value: 'savings', label: 'Con ahorro' },
            { value: 'warning', label: 'Prioritarias' },
            { value: 'info', label: 'Consejos' },
          ]}
        />
        <span className="small muted">Ordenadas por ahorro estimado</span>
      </div>

      {filtered.length === 0 ? (
        <Card className="mt-12">
          <EmptyState
            icon={<CheckCircle2 size={22} />}
            title={recommendations.length === 0 ? 'Todo en orden por ahora' : 'No hay resultados con este filtro'}
            text={
              recommendations.length === 0
                ? 'Añade más dispositivos y confirma los precios para que el motor encuentre oportunidades.'
                : 'Prueba con otro filtro para ver el resto de recomendaciones.'
            }
          />
        </Card>
      ) : (
        <div className="card-grid mt-12">
          {filtered.map((rec) => {
            const createdId = created[rec.id]
            return (
              <Card className="span-6" key={rec.id}>
                <div className={`recommendation ${rec.severity}`} style={{ border: 0, background: 'transparent' }}>
                  <div className="rec-top">
                    <div>
                      <div className="flex gap-8" style={{ flexWrap: 'wrap', marginBottom: 7 }}>
                        <Badge
                          tone={
                            rec.severity === 'high'
                              ? 'red'
                              : rec.severity === 'warning' || rec.severity === 'medium'
                                ? 'yellow'
                                : 'blue'
                          }
                        >
                          {rec.severity === 'high'
                            ? 'Prioridad alta'
                            : rec.severity === 'warning'
                              ? 'Aviso'
                              : rec.severity === 'medium'
                                ? 'Mejora'
                                : 'Consejo'}
                        </Badge>
                        <Badge tone="neutral">Confianza {confidenceLabel(rec.confidence)}</Badge>
                        {rec.device_name ? <Badge tone="neutral">{rec.device_name}</Badge> : null}
                      </div>
                      <h2 className="rec-title" style={{ fontSize: 16 }}>
                        {rec.title}
                      </h2>
                    </div>
                    <Button
                      size="sm"
                      variant="ghost"
                      aria-label="Descartar recomendación"
                      onClick={() => void dismiss(rec.id)}
                      disabled={dismissing === rec.id}
                    >
                      <X size={15} />
                    </Button>
                  </div>
                  <p className="rec-text">{rec.description}</p>
                  {rec.savings_eur_month > 0 ? (
                    <div className="rec-savings">Ahorro estimado: {eur(rec.savings_eur_month)}/mes</div>
                  ) : null}
                  <div className="banner mt-12" style={{ background: 'var(--bg-soft)' }}>
                    <CheckCircle2 size={14} style={{ flexShrink: 0, marginTop: 1, color: 'var(--accent)' }} />
                    <span>{rec.action}</span>
                  </div>
                  <div className="rec-footer">
                    <div className="flex gap-8" style={{ flexWrap: 'wrap' }}>
                      {rec.yaml ? (
                        <Button size="sm" onClick={() => setSelected(rec)}>
                          <Code2 size={13} /> Ver YAML
                        </Button>
                      ) : null}
                      {rec.can_create_automation ? (
                        createdId ? (
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => void undoAutomation(createdId, rec.id)}
                          >
                            <Trash2 size={13} /> Deshacer automatización
                          </Button>
                        ) : (
                          <Button
                            size="sm"
                            variant="primary"
                            onClick={() => void createAutomation(rec)}
                            disabled={creating === rec.id}
                          >
                            <Wand2 size={13} />{' '}
                            {creating === rec.id ? 'Creando…' : 'Crear en Home Assistant'}
                          </Button>
                        )
                      ) : rec.yaml ? (
                        <span className="small muted">Copia el YAML para usarlo en HA</span>
                      ) : null}
                    </div>
                    <span className="small muted">{rec.rule === 'shift_to_valle' ? 'Carga flexible' : ''}</span>
                  </div>
                </div>
              </Card>
            )
          })}
        </div>
      )}

      {automationsData?.items?.length ? (
        <Card className="mt-16">
          <div className="card-header">
            <div>
              <h2 className="card-title">Automatizaciones creadas desde EnergyHub</h2>
              <p className="card-subtitle">Solo se muestran las que ha creado esta app.</p>
            </div>
            <Wand2 size={17} className="muted" />
          </div>
          <div className="card-body">
            <div className="device-list">
              {automationsData.items.map((automation) => (
                <div className="device-row" key={automation.id}>
                  <div className="device-icon">
                    <Wand2 size={16} />
                  </div>
                  <div className="device-main">
                    <div className="device-name">{automation.alias}</div>
                    <div className="device-meta">
                      {automation.automation_id} · {formatDateTime(automation.created_at)}
                    </div>
                  </div>
                  <Button size="sm" variant="ghost" onClick={() => void undoAutomation(automation.automation_id, '')}>
                    <Trash2 size={13} /> Deshacer
                  </Button>
                </div>
              ))}
            </div>
          </div>
        </Card>
      ) : null}

      <Modal
        open={selected !== null}
        onClose={() => setSelected(null)}
        size="lg"
        title={selected?.title ?? 'Automatización'}
        subtitle="Revisa el YAML antes de usarlo. Las automatizaciones actúan sobre Home Assistant."
        footer={
          <>
            <Button onClick={() => setSelected(null)}>Cerrar</Button>
            {selected?.yaml ? (
              <Button
                variant="primary"
                onClick={() => void copy(selected.yaml ?? '', 'YAML copiado')}
              >
                <Copy size={14} /> Copiar YAML
              </Button>
            ) : null}
          </>
        }
      >
        {selected ? (
          <>
            <div className="banner" style={{ marginBottom: 12 }}>
              <Check size={14} style={{ flexShrink: 0, marginTop: 1, color: 'var(--success)' }} />
              <span>
                {selected.automation_kind === 'reminder'
                  ? 'Esta automatización crea un aviso en Home Assistant cuando empieza el tramo valle. No enciende nada por sí sola.'
                  : 'Esta automatización apaga el dispositivo al empezar el tramo valle. Comprueba que sea seguro antes de activarla.'}
              </span>
            </div>
            <pre className="code-block">{selected.yaml}</pre>
            {selected.copy_yaml ? (
              <>
                <div className="between mt-16" style={{ marginBottom: 8 }}>
                  <div>
                    <div className="card-title">YAML avanzado: encender en valle</div>
                    <div className="card-subtitle">
                      Cópialo solo si el aparato se puede encender de forma segura sin supervisión.
                    </div>
                  </div>
                  <Button size="sm" variant="ghost" onClick={() => void copy(selected.copy_yaml ?? '', 'YAML copiado')}>
                    <Copy size={13} /> Copiar
                  </Button>
                </div>
                <pre className="code-block">{selected.copy_yaml}</pre>
              </>
            ) : null}
          </>
        ) : null}
      </Modal>
    </div>
  )
}
