import { useState } from 'react'
import {
  BarChart3,
  CalendarClock,
  Check,
  Lightbulb,
  PlugZap,
  ShieldCheck,
  Sparkles,
} from 'lucide-react'
import { api } from '../api'
import { BoltIcon } from '../components/Icon'
import { Button, ErrorBox, Field, Input, useToast } from '../components/ui'

const FEATURES = [
  {
    icon: BarChart3,
    title: 'Factura sin sorpresas',
    text: 'Estima consumo, potencia, impuestos y factura con los precios de tu contrato.',
  },
  {
    icon: PlugZap,
    title: 'Cada aparato cuenta',
    text: 'Nevera, vitro, lavadora, TV… con potencia, horas o ciclos.',
  },
  {
    icon: CalendarClock,
    title: 'Valle, llano y punta',
    text: 'Calcula el coste por tramo y te dice cuándo merece la pena usar cada cosa.',
  },
  {
    icon: Lightbulb,
    title: 'Recomendaciones útiles',
    text: 'Ahorro estimado, hábitos y automatizaciones listas para Home Assistant.',
  },
]

export function OnboardingPage({ onComplete }: { onComplete: () => Promise<void> }) {
  const { showToast } = useToast()
  const [saving, setSaving] = useState(false)
  const [demoLoading, setDemoLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [form, setForm] = useState({
    name: 'Mi casa',
    provider: 'Pepe Energy',
    power_p1_kw: '4.6',
    power_p2_kw: '4.6',
    service_fee_eur_month: '3.996196',
    social_bond_eur_month: '0.908639',
    meter_rent_eur_month: '0.81',
    vat_rate: '0.21',
    electricity_tax_rate: '0.0511269632',
  })

  const set = (key: keyof typeof form, value: string) => setForm((current) => ({ ...current, [key]: value }))

  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    setError(null)
    setSaving(true)
    try {
      await api.saveContract({
        name: form.name,
        provider: form.provider,
        country: 'ES',
        timezone: 'Europe/Madrid',
        tariff_type: form.provider.toLowerCase().includes('pepe') ? 'pepe_variable' : 'manual',
        access_toll: '2.0TD',
        segment: '1',
        power_p1_kw: Number(form.power_p1_kw),
        power_p2_kw: Number(form.power_p2_kw),
        service_fee_eur_month: Number(form.service_fee_eur_month),
        social_bond_eur_month: Number(form.social_bond_eur_month),
        meter_rent_eur_month: Number(form.meter_rent_eur_month),
        vat_rate: Number(form.vat_rate),
        electricity_tax_rate: Number(form.electricity_tax_rate),
        currency: 'EUR',
        billing_day: 1,
      })
      // Intentamos dejar una propuesta de precios preparada; si falla, el usuario
      // podrá introducirlos manualmente desde Tarifa.
      if (form.provider.toLowerCase().includes('pepe')) {
        try {
          await api.fetchPepe()
          showToast('Contrato creado. Revisa y confirma los precios de Pepe.')
        } catch {
          showToast('Contrato creado. Añade los precios de tu tarifa en Tarifa.', 'info')
        }
      } else {
        showToast('Contrato creado. Añade los precios de tu tarifa en Tarifa.', 'info')
      }
      await onComplete()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se ha podido guardar el contrato')
    } finally {
      setSaving(false)
    }
  }

  const loadDemo = async () => {
    setDemoLoading(true)
    setError(null)
    try {
      await api.seedDemo()
      await onComplete()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se ha podido cargar la demo')
    } finally {
      setDemoLoading(false)
    }
  }

  return (
    <div className="onboarding">
      <div className="onboarding-card">
        <div className="onboarding-hero">
          <div className="flex gap-12" style={{ alignItems: 'center' }}>
            <span className="brand-mark">
              <BoltIcon size={22} />
            </span>
            <div>
              <div className="brand-name" style={{ fontSize: 18 }}>
                EnergyHub
              </div>
              <div className="brand-sub">Energía clara para tu hogar</div>
            </div>
          </div>
          <h1 className="onboarding-title">
            Tu casa consume.
            <br />
            <em>Tú decides cómo.</em>
          </h1>
          <p className="onboarding-sub">
            Convierte Home Assistant en un panel de ahorro: estima la factura, entiende qué aparato gasta
            más y descubre las horas más baratas de tu tarifa.
          </p>
          <div
            style={{
              display: 'flex',
              gap: 8,
              flexWrap: 'wrap',
              marginTop: 18,
            }}
          >
            <span className="badge badge-green">
              <Check size={12} /> Sin sensores obligatorios
            </span>
            <span className="badge badge-green">
              <Check size={12} /> Datos locales
            </span>
            <span className="badge badge-green">
              <Check size={12} /> Open source
            </span>
          </div>
        </div>

        <div className="onboarding-body">
          <div className="onboarding-panel">
            <div className="eyebrow">
              <Sparkles size={12} /> Cómo funciona
            </div>
            <div style={{ display: 'grid', gap: 2 }}>
              {FEATURES.map((feature) => {
                const Icon = feature.icon
                return (
                  <div className="feature" key={feature.title}>
                    <span className="feature-icon">
                      <Icon size={15} />
                    </span>
                    <div>
                      <div className="feature-title">{feature.title}</div>
                      <div className="feature-text">{feature.text}</div>
                    </div>
                  </div>
                )
              })}
            </div>
            <div className="banner mt-16">
              <ShieldCheck size={15} style={{ flexShrink: 0, marginTop: 1 }} />
              <span>
                Tus datos se guardan en el almacenamiento de la app dentro de Home Assistant. Nada se envía
                a servidores de EnergyHub.
              </span>
            </div>
          </div>

          <div className="onboarding-panel">
            <div className="eyebrow">
              <PlugZap size={12} /> Empezar
            </div>
            <h2 style={{ margin: '0 0 5px', fontSize: 20, letterSpacing: '-0.035em' }}>
              Configura tu contrato
            </h2>
            <p className="small muted" style={{ marginTop: 0 }}>
              Viene precargado con la Tarifa Variable de Pepe Energy y 2.0TD. Puedes ajustar todos los
              valores.
            </p>
            {error ? <ErrorBox message={error} /> : null}
            <form onSubmit={submit} style={{ display: 'grid', gap: 13, marginTop: 14 }}>
              <div className="form-grid">
                <Field label="Nombre del contrato">
                  <Input value={form.name} onChange={(event) => set('name', event.target.value)} required />
                </Field>
                <Field label="Comercializadora">
                  <Input
                    value={form.provider}
                    onChange={(event) => set('provider', event.target.value)}
                    required
                  />
                </Field>
              </div>
              <div className="form-grid">
                <Field label="Potencia P1 (kW)" hint="Punta y llano">
                  <Input
                    type="number"
                    step="0.01"
                    min="0"
                    value={form.power_p1_kw}
                    onChange={(event) => set('power_p1_kw', event.target.value)}
                    required
                  />
                </Field>
                <Field label="Potencia P2 (kW)" hint="Valle">
                  <Input
                    type="number"
                    step="0.01"
                    min="0"
                    value={form.power_p2_kw}
                    onChange={(event) => set('power_p2_kw', event.target.value)}
                    required
                  />
                </Field>
              </div>
              <div className="form-grid">
                <Field label="Cuota de servicio (€/mes)" hint="Impuestos incluidos">
                  <Input
                    type="number"
                    step="any"
                    min="0"
                    value={form.service_fee_eur_month}
                    onChange={(event) => set('service_fee_eur_month', event.target.value)}
                  />
                </Field>
                <Field label="Bono social (€/mes)" hint="Impuestos incluidos">
                  <Input
                    type="number"
                    step="any"
                    min="0"
                    value={form.social_bond_eur_month}
                    onChange={(event) => set('social_bond_eur_month', event.target.value)}
                  />
                </Field>
              </div>
              <div className="form-grid-3">
                <Field label="Alquiler contador (€/mes)">
                  <Input
                    type="number"
                    step="0.01"
                    min="0"
                    value={form.meter_rent_eur_month}
                    onChange={(event) => set('meter_rent_eur_month', event.target.value)}
                  />
                </Field>
                <Field label="IVA" hint="21 % por defecto">
                  <Input
                    type="number"
                    step="0.01"
                    min="0"
                    max="1"
                    value={form.vat_rate}
                    onChange={(event) => set('vat_rate', event.target.value)}
                  />
                </Field>
                <Field label="Impuesto eléctrico" hint="5,113 % por defecto">
                  <Input
                    type="number"
                    step="any"
                    min="0"
                    max="1"
                    value={form.electricity_tax_rate}
                    onChange={(event) => set('electricity_tax_rate', event.target.value)}
                  />
                </Field>
              </div>
              <Button type="submit" variant="primary" className="w-full" disabled={saving}>
                {saving ? 'Guardando…' : 'Crear contrato y empezar'}
              </Button>
            </form>
            <div className="between mt-16" style={{ gap: 10 }}>
              <span className="small muted">¿Solo quieres verlo primero?</span>
              <Button type="button" variant="ghost" size="sm" onClick={loadDemo} disabled={demoLoading}>
                {demoLoading ? 'Cargando…' : 'Probar con datos de ejemplo'}
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
