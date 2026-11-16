import { useEffect, useState, type ReactNode } from 'react'
import { NavLink } from 'react-router-dom'
import {
  BarChart3,
  CalendarClock,
  Gauge,
  Lightbulb,
  Moon,
  Plug,
  Settings2,
  Sparkles,
  Sun,
  Zap,
} from 'lucide-react'
import { BoltIcon } from './Icon'
import { Badge } from './ui'
import { cn } from '../lib/format'
import type { Bootstrap } from '../types'

const NAV = [
  { to: '/', label: 'Resumen', icon: Gauge, end: true },
  { to: '/devices', label: 'Dispositivos', icon: Plug },
  { to: '/tariff', label: 'Tarifa', icon: BarChart3 },
  { to: '/schedule', label: 'Horarios', icon: CalendarClock },
  { to: '/recommendations', label: 'Recomendaciones', icon: Lightbulb },
  { to: '/changelog', label: 'Novedades', icon: Sparkles },
  { to: '/settings', label: 'Ajustes', icon: Settings2 },
]

function getInitialTheme(): 'dark' | 'light' {
  const stored = localStorage.getItem('energyhub-theme')
  if (stored === 'light' || stored === 'dark') return stored
  return window.matchMedia?.('(prefers-color-scheme: light)').matches ? 'light' : 'dark'
}

export function Layout({
  children,
  bootstrap,
  recommendationsCount,
}: {
  children: ReactNode
  bootstrap: Bootstrap
  recommendationsCount: number
}) {
  const [theme, setTheme] = useState<'dark' | 'light'>(getInitialTheme)

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    localStorage.setItem('energyhub-theme', theme)
  }, [theme])

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <NavLink to="/" className="brand" aria-label="EnergyHub, ir al resumen">
          <span className="brand-mark">
            <BoltIcon />
          </span>
          <span>
            <span className="brand-name">EnergyHub</span>
            <span className="brand-sub">Energía clara</span>
          </span>
        </NavLink>

        <nav className="nav" aria-label="Navegación principal">
          <div className="nav-label">Panel</div>
          {NAV.map((item) => {
            const Icon = item.icon
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) => cn('nav-link', isActive && 'active')}
              >
                <Icon size={17} strokeWidth={1.9} />
                <span>{item.label}</span>
                {item.to === '/recommendations' && recommendationsCount > 0 ? (
                  <span className="nav-badge">{recommendationsCount}</span>
                ) : null}
              </NavLink>
            )
          })}
        </nav>

        <div className="sidebar-footer">
          {bootstrap.demo_mode ? (
            <div className="sidebar-note">
              <strong>Datos de ejemplo</strong>
              Estás explorando EnergyHub con una casa simulada.
            </div>
          ) : null}
          <div className="sidebar-note">
            <strong>{bootstrap.ha.connected ? 'Home Assistant conectado' : 'Sin conexión con HA'}</strong>
            {bootstrap.ha.connected
              ? `Versión ${bootstrap.ha.version ?? '—'}`
              : 'Puedes usar la estimación manual y conectar HA después.'}
          </div>
          <button
            type="button"
            className="theme-button"
            onClick={() => setTheme((value) => (value === 'dark' ? 'light' : 'dark'))}
          >
            <span className="flex gap-8" style={{ alignItems: 'center' }}>
              {theme === 'dark' ? <Moon size={14} /> : <Sun size={14} />}
              {theme === 'dark' ? 'Tema oscuro' : 'Tema claro'}
            </span>
            <Badge tone="neutral">v{bootstrap.app_version}</Badge>
          </button>
        </div>
      </aside>

      <main className="main">
        {bootstrap.demo_mode ? (
          <div className="banner accent" style={{ marginBottom: 16 }}>
            <Zap size={15} style={{ flexShrink: 0, marginTop: 1 }} />
            <span>
              <strong>Modo demo.</strong> Los datos son de ejemplo. Puedes empezar de cero desde Ajustes.
            </span>
          </div>
        ) : null}
        {children}
      </main>
    </div>
  )
}
