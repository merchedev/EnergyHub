import {
  ArrowUpCircle,
  CheckCircle2,
  ExternalLink,
  Info,
  PackageCheck,
  RefreshCw,
  Server,
  Sparkles,
} from 'lucide-react'
import { api } from '../api'
import {
  Badge,
  Banner,
  Button,
  Card,
  ErrorBox,
  Loading,
} from '../components/ui'
import { useApi } from '../hooks/useApi'
import { formatDate } from '../lib/format'
import type { ChangelogResponse } from '../types'

function sourceLabel(source: ChangelogResponse['source']): string {
  if (source === 'supervisor') return 'Tienda de Home Assistant'
  if (source === 'github') return 'GitHub'
  return 'Changelog incluido en la app'
}

export function ChangelogPage() {
  const { data, loading, error, reload } = useApi<ChangelogResponse>('/changelog')
  const openAppsPage = () => {
    const url = new URL('/config/apps', window.location.origin).toString()
    window.open(url, '_blank', 'noopener,noreferrer')
  }

  if (loading && !data) return <Loading label="Consultando novedades…" />
  if (error && !data) {
    return (
      <div className="page">
        <ErrorBox message={error} />
        <Button className="mt-12" onClick={() => void reload()}>
          <RefreshCw size={14} /> Reintentar
        </Button>
      </div>
    )
  }
  if (!data) return null

  const hasUpdates = data.update_available
  const hasEntries = data.entries.length > 0

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <div className="eyebrow">
            <Sparkles size={12} /> Novedades
          </div>
          <h1 className="page-title">Lo que cambia en EnergyHub.</h1>
          <p className="page-subtitle">
            Solo mostramos las versiones posteriores a la que tienes instalada. Si estás al día, no hay
            ruido: te lo decimos y punto.
          </p>
        </div>
        <div className="actions">
          <Button onClick={() => void reload()}>
            <RefreshCw size={14} /> Comprobar de nuevo
          </Button>
          <Button
            variant="secondary"
            onClick={() => window.open(data.full_changelog_url, '_blank', 'noopener,noreferrer')}
          >
            Changelog completo <ExternalLink size={13} />
          </Button>
        </div>
      </div>

      <div className="hero mt-16">
        <div className="hero-content">
          <div>
            <div className="hero-kicker">
              <span>Versión instalada</span>
              <Badge tone="neutral">v{data.installed_version}</Badge>
              <Badge tone={data.checked ? 'green' : 'yellow'}>
                <Server size={11} /> {sourceLabel(data.source)}
              </Badge>
            </div>
            <p className="hero-label">
              {hasUpdates ? 'Nueva versión disponible' : data.checked ? 'Estado' : 'No se pudo comprobar'}
            </p>
            <div className="hero-amount" style={{ fontSize: 'clamp(32px, 4.5vw, 52px)' }}>
              {hasUpdates ? `v${data.latest_version}` : `v${data.installed_version}`}
            </div>
            <div className="hero-meta">
              {hasUpdates
                ? 'Hay versiones pendientes de instalar. Revisa las notas antes de actualizar.'
                : data.checked
                  ? 'No hay versiones posteriores a la instalada.'
                  : 'La tienda de Home Assistant no ha respondido; este es el changelog incluido en la app.'}
            </div>
          </div>
          <div className="hero-side">
            {hasUpdates ? (
              <div className="hero-actions">
                <Button variant="primary" onClick={openAppsPage}>
                  Abrir Apps de HA <ArrowUpCircle size={14} />
                </Button>
              </div>
            ) : null}
            <div className="small muted" style={{ maxWidth: 230, textAlign: 'right' }}>
              {hasUpdates
                ? 'Home Assistant → Ajustes → Apps → EnergyHub → Actualizar.'
                : 'También puedes consultar el historial completo en GitHub.'}
            </div>
          </div>
        </div>
      </div>

      {data.error ? (
        <Banner tone="warning">
          <Info size={15} style={{ flexShrink: 0, marginTop: 1 }} />
          <span>{data.error}</span>
        </Banner>
      ) : null}

      {!hasUpdates && data.checked ? (
        <Banner tone="accent">
          <CheckCircle2 size={15} style={{ flexShrink: 0, marginTop: 1 }} />
          <span>
            <strong>Estás al día.</strong> No hay versiones pendientes de instalar. Cuando publiquemos una
            nueva, aparecerá aquí con sus notas.
          </span>
        </Banner>
      ) : null}

      {!data.checked && !hasUpdates ? (
        <Banner tone="warning">
          <Info size={15} style={{ flexShrink: 0, marginTop: 1 }} />
          <span>
            No se ha podido consultar la tienda de Home Assistant ni GitHub. No podemos confirmar si hay
            una versión nueva; revisa la app store de Home Assistant.
          </span>
        </Banner>
      ) : null}

      {hasUpdates && !hasEntries ? (
        <Card className="mt-16">
          <div className="card-body">
            <div className="flex gap-12" style={{ alignItems: 'flex-start' }}>
              <div className="empty-icon" style={{ width: 42, height: 42, flexShrink: 0 }}>
                <PackageCheck size={20} />
              </div>
              <div>
                <div className="card-title">Hay una versión nueva: v{data.latest_version}</div>
                <div className="card-subtitle">
                  La tienda no ha devuelto las notas de esta versión. Puedes actualizar desde Home
                  Assistant o consultar el changelog completo en GitHub.
                </div>
              </div>
            </div>
          </div>
        </Card>
      ) : null}

      {hasEntries ? (
        <div className="card-grid mt-16">
          {data.entries.map((entry) => (
            <Card className="span-6" key={entry.version}>
              <div className="card-header">
                <div>
                  <div className="flex gap-8" style={{ alignItems: 'center', flexWrap: 'wrap' }}>
                    <h2 className="card-title" style={{ fontSize: 18 }}>
                      v{entry.version}
                    </h2>
                    <Badge tone="green">Disponible</Badge>
                    {entry.date ? <Badge tone="neutral">{formatDate(entry.date)}</Badge> : null}
                  </div>
                  <p className="card-subtitle">Cambios incluidos en esta versión.</p>
                </div>
                <Sparkles size={16} className="muted" />
              </div>
              <div className="card-body">
                <ul className="changelog-list">
                  {entry.notes.map((note, index) => (
                    <li key={`${entry.version}-${index}`}>{note}</li>
                  ))}
                </ul>
              </div>
            </Card>
          ))}
        </div>
      ) : null}

      {hasUpdates ? (
        <div className="banner mt-16">
          <Info size={15} style={{ flexShrink: 0, marginTop: 1 }} />
          <span>
            Solo se muestran las versiones posteriores a la instalada. El historial completo está en el
            enlace superior y en el archivo <code>CHANGELOG.md</code> de la app.
          </span>
        </div>
      ) : null}
    </div>
  )
}
