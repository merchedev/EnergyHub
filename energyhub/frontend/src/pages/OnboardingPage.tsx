import { useEffect, useMemo, useState } from 'react'
import {
  BarChart3,
  CalendarClock,
  Check,
  ChevronDown,
  Lightbulb,
  PlugZap,
  ShieldCheck,
  Sparkles,
  Zap,
} from 'lucide-react'
import { api } from '../api'
import { BoltIcon } from '../components/Icon'
import { Button, ErrorBox, Field, Input, Loading, Select, Toggle, useToast } from '../components/ui'
import { useApi } from '../hooks/useApi'
import type { BonoSocialCategory, TariffProfile, TariffsResponse } from '../types'

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

const BONO_LIMITS = [
  { value: '1587', label: '1.587 kWh/año · una o dos personas' },
  { value: '2222', label: '2.222 kWh/año · tres personas, pensionistas o dos con un menor' },
  { value: '2698', label: '2.698 kWh/año · cuatro personas o tres con dos menores' },
  { value: '4761', label: '4.761 kWh/año · cinco o más, familias numerosas…' },
]

export function OnboardingPage({ onComplete }: { onComplete: () => Promise<void> }) {
  const { showToast } = useToast()
  const { data: tariffData, loading: tariffsLoading, error: tariffsError } = useApi<TariffsResponse>('/tariffs')
  const [selectedProfileId, setSelectedProfileId] = useState('pepe_variable')
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
    has_pepephone_discount: false,
    bono_social_category: 'none' as BonoSocialCategory,
    bono_social_energy_limit_kwh: '1587',
  })

  const profiles = tariffData?.profiles ?? []
  const selectedProfile = useMemo(
    () => profiles.find((profile) => profile.id === selectedProfileId) ?? profiles[0],
    [profiles, selectedProfileId],
  )
  const companies = useMemo(() => {
    const seen = new Map<string, TariffProfile>()
    for (const profile of profiles) {
      if (!seen.has(profile.company)) seen.set(profile.company, profile)
    }
    return [...seen.values()]
  }, [profiles])

  useEffect(() => {
    if (!selectedProfile) return
    setForm((current) => ({
      ...current,
      provider: selectedProfile.company,
      service_fee_eur_month: String(selectedProfile.service_fee_eur_month),
      social_bond_eur_month: String(selectedProfile.social_bond_eur_month),
      meter_rent_eur_month: String(selectedProfile.meter_rent_eur_month),
      vat_rate: String(selectedProfile.vat_rate),
      electricity_tax_rate: String(selectedProfile.electricity_tax_rate),
      has_pepephone_discount: selectedProfile.supports_pepephone_discount
        ? current.has_pepephone_discount
        : false,
      bono_social_category: selectedProfile.bono_social_eligible
        ? current.bono_social_category
        : 'none',
    }))
  }, [selectedProfile])

  useEffect(() => {
    if (!selectedProfileId && profiles.length > 0) {
      setSelectedProfileId(profiles[0].id)
    }
  }, [profiles, selectedProfileId])

  const set = (key: keyof typeof form, value: string | boolean) =>
    setForm((current) => ({ ...current, [key]: value }))

  const selectCompany = (company: string) => {
    const profile = companies.find((item) => item.company === company)
    if (profile) setSelectedProfileId(profile.id)
  }

  const togglePepephone = (value: boolean) => {
    setForm((current) => ({
      ...current,
      has_pepephone_discount: value,
      service_fee_eur_month:
        value && selectedProfile?.supports_pepephone_discount
          ? '0'
          : String(selectedProfile?.service_fee_eur_month ?? 0),
    }))
  }

  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!selectedProfile) return
    setError(null)
    setSaving(true)
    try {
      await api.saveContract({
        name: form.name,
        provider: form.provider,
        country: 'ES',
        timezone: 'Europe/Madrid',
        tariff_type: selectedProfile.kind,
        tariff_profile_id: selectedProfile.id,
        access_toll: selectedProfile.access_toll,
        segment: '1',
        power_p1_kw: Number(form.power_p1_kw),
        power_p2_kw: Number(form.power_p2_kw),
        service_fee_eur_month: Number(form.service_fee_eur_month),
        social_bond_eur_month: Number(form.social_bond_eur_month),
        meter_rent_eur_month: Number(form.meter_rent_eur_month),
        vat_rate: Number(form.vat_rate),
        electricity_tax_rate: Number(form.electricity_tax_rate),
        has_pepephone_discount: form.has_pepephone_discount,
        bono_social_category: form.bono_social_category,
        bono_social_energy_limit_kwh: Number(form.bono_social_energy_limit_kwh),
        currency: 'EUR',
        billing_day: 1,
      })
      if (selectedProfile.price_source.startsWith('pepe_api')) {
        try {
          await api.fetchPepe()
          showToast('Contrato creado. Revisa y confirma los precios de Pepe.')
        } catch {
          showToast('Contrato creado. Confirma los precios en Tarifa.', 'info')
        }
      } else if (selectedProfile.price_source === 'ree_pvpc') {
        showToast('Contrato PVPC creado. Cargando precios horarios…')
      } else {
        showToast('Contrato creado. Introduce los precios de tu tarifa en Tarifa.', 'info')
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

  if (tariffsLoading || !tariffData) {
    return (
      <div className="onboarding">
        <div style={{ width: 360 }}>
          <Loading label="Cargando tarifas…" />
          {tariffsError ? <ErrorBox message={tariffsError} /> : null}
        </div>
      </div>
    )
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
            Elige tu compañía y tarifa. La app rellena los precios, la cuota y los impuestos; tú solo
            confirmas la potencia y los precios.
          </p>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 18 }}>
            <span className="badge badge-green">
              <Check size={12} /> Precios Pepe y PVPC automáticos
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
              Empieza por tu compañía. Los campos avanzados ya vendrán rellenos.
            </p>
            {error ? <ErrorBox message={error} /> : null}
            <form onSubmit={submit} style={{ display: 'grid', gap: 13, marginTop: 14 }}>
              <div className="form-grid">
                <Field label="Nombre del contrato">
                  <Input value={form.name} onChange={(event) => set('name', event.target.value)} required />
                </Field>
                <Field label="Comercializadora">
                  <Select
                    value={selectedProfile?.company ?? ''}
                    onChange={(event) => selectCompany(event.target.value)}
                  >
                    {companies.map((company) => (
                      <option key={company.company} value={company.company}>
                        {company.company}
                      </option>
                    ))}
                  </Select>
                </Field>
              </div>
              <Field
                label="Tarifa"
                hint={
                  selectedProfile
                    ? `${selectedProfile.notes}${selectedProfile.last_updated ? ` Actualizado: ${selectedProfile.last_updated}.` : ''}`
                    : undefined
                }
              >
                <Select
                  value={selectedProfileId}
                  onChange={(event) => setSelectedProfileId(event.target.value)}
                >
                  {profiles
                    .filter((profile) => profile.company === selectedProfile?.company)
                    .map((profile) => (
                      <option key={profile.id} value={profile.id}>
                        {profile.name}
                      </option>
                    ))}
                </Select>
              </Field>
              <div className="flex gap-8" style={{ flexWrap: 'wrap' }}>
                {selectedProfile?.price_source.startsWith('pepe_api') ? (
                  <span className="badge badge-green">
                    <Zap size={11} /> Precios automáticos de Pepe
                  </span>
                ) : selectedProfile?.price_source === 'ree_pvpc' ? (
                  <span className="badge badge-green">
                    <Zap size={11} /> PVPC horario automático
                  </span>
                ) : (
                  <span className="badge badge-yellow">Precios manuales · confirma tu factura</span>
                )}
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
              {selectedProfile?.supports_pepephone_discount ? (
                <Toggle
                  checked={form.has_pepephone_discount}
                  onChange={togglePepephone}
                  label="Soy cliente de Pepephone"
                  hint="La cuota de servicio de Pepe pasa a 0 €/mes."
                />
              ) : null}
              {selectedProfile?.bono_social_eligible ? (
                <div className="banner accent">
                  <Lightbulb size={15} style={{ flexShrink: 0, marginTop: 1 }} />
                  <span>
                    <strong>Bono social (solo PVPC).</strong> Si eres beneficiario, indica la categoría y el
                    límite anual. La financiación regulada ya está incluida en la factura.
                  </span>
                </div>
              ) : null}
              {selectedProfile?.bono_social_eligible ? (
                <div className="form-grid">
                  <Field label="Categoría de bono social">
                    <Select
                      value={form.bono_social_category}
                      onChange={(event) => set('bono_social_category', event.target.value)}
                    >
                      <option value="none">No soy beneficiario</option>
                      <option value="vulnerable">Vulnerable · 42,5 %</option>
                      <option value="severe">Vulnerable severo · 57,5 %</option>
                      <option value="exclusion">Riesgo de exclusión · 100 %</option>
                    </Select>
                  </Field>
                  <Field label="Límite anual de energía">
                    <Select
                      value={form.bono_social_energy_limit_kwh}
                      onChange={(event) => set('bono_social_energy_limit_kwh', event.target.value)}
                    >
                      {BONO_LIMITS.map((limit) => (
                        <option key={limit.value} value={limit.value}>
                          {limit.label}
                        </option>
                      ))}
                    </Select>
                  </Field>
                </div>
              ) : null}
              <details className="advanced-block">
                <summary>
                  <span>Avanzado: cuota, bono social, alquiler e impuestos</span>
                  <ChevronDown size={14} />
                </summary>
                <div className="form-grid mt-12">
                  <Field label="Cuota de servicio (€/mes)" hint="Impuestos incluidos">
                    <Input
                      type="number"
                      step="any"
                      min="0"
                      value={form.service_fee_eur_month}
                      onChange={(event) => set('service_fee_eur_month', event.target.value)}
                    />
                  </Field>
                  <Field label="Financiación del bono social (€/mes)" hint="Impuestos incluidos">
                    <Input
                      type="number"
                      step="any"
                      min="0"
                      value={form.social_bond_eur_month}
                      onChange={(event) => set('social_bond_eur_month', event.target.value)}
                    />
                  </Field>
                  <Field label="Alquiler de contador (€/mes)">
                    <Input
                      type="number"
                      step="any"
                      min="0"
                      value={form.meter_rent_eur_month}
                      onChange={(event) => set('meter_rent_eur_month', event.target.value)}
                    />
                  </Field>
                  <Field label="IVA" hint="21 % por defecto">
                    <Input
                      type="number"
                      step="any"
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
              </details>
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
