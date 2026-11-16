import { useCallback, useEffect, useState } from 'react'
import { Route, Routes } from 'react-router-dom'
import { api } from './api'
import { Layout } from './components/Layout'
import { Loading, ErrorBox } from './components/ui'
import { OnboardingPage } from './pages/OnboardingPage'
import { DashboardPage } from './pages/DashboardPage'
import { DevicesPage } from './pages/DevicesPage'
import { TariffPage } from './pages/TariffPage'
import { SchedulePage } from './pages/SchedulePage'
import { RecommendationsPage } from './pages/RecommendationsPage'
import { ChangelogPage } from './pages/ChangelogPage'
import { SettingsPage } from './pages/SettingsPage'
import type { Bootstrap } from './types'

export function App() {
  const [bootstrap, setBootstrap] = useState<Bootstrap | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [recommendationsCount, setRecommendationsCount] = useState(0)

  const refreshBootstrap = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await api.bootstrap()
      setBootstrap(result)
      if (result.has_contract) {
        try {
          const recs = await api.recommendations()
          setRecommendationsCount(recs.items.length)
        } catch {
          setRecommendationsCount(0)
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se ha podido conectar con el backend')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refreshBootstrap()
  }, [refreshBootstrap])

  if (loading && !bootstrap) {
    return (
      <div className="onboarding">
        <div style={{ width: 320 }}>
          <Loading label="Iniciando EnergyHub…" />
        </div>
      </div>
    )
  }

  if (error && !bootstrap) {
    return (
      <div className="onboarding">
        <div style={{ width: 'min(560px, 100%)' }}>
          <ErrorBox message={error} />
          <p className="small muted mt-12">
            Comprueba que el backend de EnergyHub está ejecutándose y recarga la página.
          </p>
        </div>
      </div>
    )
  }

  if (!bootstrap) return null

  if (!bootstrap.has_contract) {
    return <OnboardingPage onComplete={refreshBootstrap} />
  }

  return (
    <Layout bootstrap={bootstrap} recommendationsCount={recommendationsCount}>
      <Routes>
        <Route path="/" element={<DashboardPage onChanged={refreshBootstrap} />} />
        <Route path="/devices" element={<DevicesPage />} />
        <Route path="/tariff" element={<TariffPage onChanged={refreshBootstrap} />} />
        <Route path="/schedule" element={<SchedulePage />} />
        <Route
          path="/recommendations"
          element={<RecommendationsPage onCountChange={setRecommendationsCount} />}
        />
        <Route path="/changelog" element={<ChangelogPage />} />
        <Route path="/settings" element={<SettingsPage onChanged={refreshBootstrap} />} />
        <Route path="*" element={<DashboardPage onChanged={refreshBootstrap} />} />
      </Routes>
    </Layout>
  )
}
