import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  BadgeEuro,
  CalendarDays,
  Check,
  CloudDownload,
  Coins,
  ExternalLink,
  FileText,
  Gauge,
  Info,
  Landmark,
  Link2,
  RefreshCw,
  Save,
  SlidersHorizontal,
  Sparkles,
  Zap,
} from 'lucide-react'
import { api } from '../api'
import {
  Badge,
  Banner,
  Button,
  Card,
  ErrorBox,
  Field,
  Input,
  Loading,
  Modal,
  Select,
  Tabs,
  Toggle,
  useToast,
} from '../components/ui'
import { useApi } from '../hooks/useApi'
import {
  formatDate,
  formatDateTime,
  eur,
  monthInputValue,
  pricePerKwh,
  pricePerKwDay,
} from '../lib/format'
import type {
  BonoSocialCategory,
  Calibration,
  ComparatorResponse,
  Contract,
  FixedBreakdown,
  HaEntity,
  PriceInfo,
  PriceProposal,
  TariffProfile,
  TariffsResponse,
} from '../types'

type Tab = 'contract' | 'prices' | 'bill' | 'comparator' | 'esios'

const TAB_VALUES: Tab[] = ['contract', 'prices', 'bill', 'comparator', 'esios']

function isTab(value: string | null): value is Tab {
  return value !== null && TAB_VALUES.includes(value as Tab)
}

interface CurrentTariffResponse {
  contract: Contract
  profile: TariffProfile
  month: string
  month_label: string
  days: number
  price: PriceInfo | null
  periods: Array<{ id: string; name: string; price: number }>
  fixed: FixedBreakdown | null
  price_mode: 'hourly' | 'period'
  calibration_factor: number
  calibration: Calibration | null
}

const BONO_LIMITS = [
  { value: '1587', label: '1.587 kWh/año' },
  { value: '2222', label: '2.222 kWh/año' },
  { value: '2698', label: '2.698 kWh/año' },
  { value: '4761', label: '4.761 kWh/año' },
]

const REGIONS = [
  { value: '', label: 'Festivos nacionales' },
  { value: 'AN', label: 'Andalucía' },
  { value: 'AR', label: 'Aragón' },
  { value: 'AS', label: 'Asturias' },
  { value: 'CB', label: 'Cantabria' },
  { value: 'CL', label: 'Castilla y León' },
  { value: 'CM', label: 'Castilla-La Mancha' },
  { value: 'CT', label: 'Cataluña' },
  { value: 'EX', label: 'Extremadura' },
  { value: 'GA', label: 'Galicia' },
  { value: 'IB', label: 'Islas Baleares' },
  { value: 'IC', label: 'Islas Canarias' },
  { value: 'MC', label: 'Murcia' },
  { value: 'MD', label: 'Madrid' },
  { value: 'NC', label: 'Navarra' },
  { value: 'PV', label: 'País Vasco' },
  { value: 'RI', label: 'La Rioja' },
  { value: 'VC', label: 'Valencia' },
  { value: 'CE', label: 'Ceuta' },
  { value: 'ML', label: 'Melilla' },
]

function contractToForm(contract: Contract) {
  return {
    name: contract.name,
    provider: contract.provider,
    tariff_profile_id: contract.tariff_profile_id,
    region: contract.region ?? '',
    power_p1_kw: String(contract.power_p1_kw),
    power_p2_kw: String(contract.power_p2_kw),
    service_fee_eur_month: String(contract.service_fee_eur_month),
    social_bond_eur_month: String(contract.social_bond_eur_month),
    meter_rent_eur_month: String(contract.meter_rent_eur_month),
    other_fees_eur_month: String(contract.other_fees_eur_month),
    vat_rate: String(contract.vat_rate),
    electricity_tax_rate: String(contract.electricity_tax_rate),
    has_pepephone_discount: contract.has_pepephone_discount,
    bono_social_category: contract.bono_social_category,
    bono_social_energy_limit_kwh: String(contract.bono_social_energy_limit_kwh),
  }
}

function profileToForm(contractForm: ReturnType<typeof contractToForm>, profile: TariffProfile) {
  return {
    ...contractForm,
    provider: profile.company,
    tariff_profile_id: profile.id,
    service_fee_eur_month: String(profile.service_fee_eur_month),
    social_bond_eur_month: String(profile.social_bond_eur_month),
    meter_rent_eur_month: String(profile.meter_rent_eur_month),
    vat_rate: String(profile.vat_rate),
    electricity_tax_rate: String(profile.electricity_tax_rate),
    has_pepephone_discount: profile.supports_pepephone_discount
      ? contractForm.has_pepephone_discount
      : false,
    bono_social_category: profile.bono_social_eligible ? contractForm.bono_social_category : 'none',
  }
}

export function TariffPage({ onChanged }: { onChanged: () => Promise<void> }) {
  const { showToast } = useToast()
  const { data, loading, error, reload } = useApi<CurrentTariffResponse>('/tariff/current')
  const { data: proposalsData, reload: reloadProposals } = useApi<{ items: PriceProposal[] }>(
    '/tariff/proposals',
  )
  const { data: calibrationsData, reload: reloadCalibrations } = useApi<{
    items: Calibration[]
    factor: number
  }>('/calibrations')
  const { data: settings } = useApi<{ esios_entity_id: string }>('/settings')
  const { data: priceEntities } = useApi<{ configured: boolean; items: HaEntity[] }>('/ha/entities?kind=price')
  const { data: tariffsData } = useApi<TariffsResponse>('/tariffs')
  const [comparatorMonth, setComparatorMonth] = useState(() => {
    const previous = new Date()
    previous.setMonth(previous.getMonth() - 1)
    return monthInputValue(previous)
  })
  const {
    data: comparatorData,
    loading: comparatorLoading,
    error: comparatorError,
    reload: reloadComparator,
  } = useApi<ComparatorResponse>(`/comparator?month=${comparatorMonth}`)

  const [searchParams] = useSearchParams()
  const [tab, setTab] = useState<Tab>(() => {
    const requested = searchParams.get('tab')
    return isTab(requested) ? requested : 'contract'
  })

  useEffect(() => {
    const requested = searchParams.get('tab')
    if (isTab(requested)) setTab(requested)
  }, [searchParams])
  const [contractForm, setContractForm] = useState(() =>
    data?.contract
      ? contractToForm(data.contract)
      : {
          name: 'Mi casa',
          provider: 'Pepe Energy',
          tariff_profile_id: 'pepe_variable',
          region: '',
          power_p1_kw: '4.6',
          power_p2_kw: '4.6',
          service_fee_eur_month: '3.996196',
          social_bond_eur_month: '0.908639',
          meter_rent_eur_month: '0.81',
          other_fees_eur_month: '0',
          vat_rate: '0.21',
          electricity_tax_rate: '0.0511269632',
          has_pepephone_discount: false,
          bono_social_category: 'none' as BonoSocialCategory,
          bono_social_energy_limit_kwh: '1587',
        },
  )
  const [savingContract, setSavingContract] = useState(false)
  const [manualOpen, setManualOpen] = useState(false)
  const [manual, setManual] = useState({
    month: monthInputValue(),
    p1_price: '',
    p2_price: '',
    p3_price: '',
    power_p1_price: '',
    power_p2_price: '',
    service_fee_eur_month: '',
    social_bond_eur_month: '',
    vat_rate: '0.21',
    electricity_tax_rate: '0.0511269632',
  })
  const [manualSaving, setManualSaving] = useState(false)
  const [pepeLoading, setPepeLoading] = useState(false)
  const [pepeError, setPepeError] = useState<string | null>(null)
  const [proposal, setProposal] = useState<PriceProposal | null>(null)
  const [confirming, setConfirming] = useState(false)
  const [calibration, setCalibration] = useState({
    month: monthInputValue(),
    actual_kwh: '',
    actual_cost_eur: '',
    notes: '',
  })
  const [calibrating, setCalibrating] = useState(false)
  const [calibrationResult, setCalibrationResult] = useState<{
    factor: number
    estimated_kwh: number
    estimated_cost: number
  } | null>(null)
  const [esiosEntity, setEsiosEntity] = useState('')
  const [savingEsios, setSavingEsios] = useState(false)
  const [errorLocal, setErrorLocal] = useState<string | null>(null)

  useEffect(() => {
    if (data?.contract) setContractForm(contractToForm(data.contract))
  }, [data?.contract])

  useEffect(() => {
    if (data?.price) {
      setManual((current) => ({
        ...current,
        p1_price: String(data.price?.p1_price ?? ''),
        p2_price: String(data.price?.p2_price ?? ''),
        p3_price: String(data.price?.p3_price ?? ''),
        power_p1_price: String(data.price?.power_p1_price ?? ''),
        power_p2_price: String(data.price?.power_p2_price ?? ''),
        service_fee_eur_month: String(data.price?.service_fee_eur_month ?? data.contract.service_fee_eur_month),
        social_bond_eur_month: String(data.price?.social_bond_eur_month ?? data.contract.social_bond_eur_month),
        vat_rate: String(data.price?.vat_rate ?? data.contract.vat_rate),
        electricity_tax_rate: String(
          data.price?.electricity_tax_rate ?? data.contract.electricity_tax_rate,
        ),
      }))
    }
  }, [data?.price, data?.contract])

  useEffect(() => {
    if (settings?.esios_entity_id) setEsiosEntity(settings.esios_entity_id)
  }, [settings?.esios_entity_id])

  const pendingProposals = useMemo(
    () => (proposalsData?.items ?? []).filter((item) => item.status === 'pending'),
    [proposalsData],
  )

  const profiles = tariffsData?.profiles ?? []
  const selectedProfile =
    profiles.find((profile) => profile.id === contractForm.tariff_profile_id) ?? data?.profile

  const setContract = (key: keyof typeof contractForm, value: string | boolean) =>
    setContractForm((current) => ({ ...current, [key]: value }))

  const applyProfile = (profileId: string) => {
    const profile = profiles.find((item) => item.id === profileId)
    if (!profile) return
    setContractForm((current) => profileToForm(current, profile))
  }

  const togglePepephone = (value: boolean) => {
    setContractForm((current) => ({
      ...current,
      has_pepephone_discount: value,
      service_fee_eur_month:
        value && selectedProfile?.supports_pepephone_discount
          ? '0'
          : String(selectedProfile?.service_fee_eur_month ?? 0),
    }))
  }

  const saveContract = async () => {
    setErrorLocal(null)
    setSavingContract(true)
    try {
      await api.saveContract({
        name: contractForm.name,
        provider: contractForm.provider,
        region: contractForm.region || null,
        country: 'ES',
        timezone: 'Europe/Madrid',
        tariff_type: selectedProfile?.kind ?? 'manual',
        tariff_profile_id: contractForm.tariff_profile_id,
        access_toll: selectedProfile?.access_toll ?? '2.0TD',
        segment: '1',
        power_p1_kw: Number(contractForm.power_p1_kw),
        power_p2_kw: Number(contractForm.power_p2_kw),
        service_fee_eur_month: Number(contractForm.service_fee_eur_month),
        social_bond_eur_month: Number(contractForm.social_bond_eur_month),
        meter_rent_eur_month: Number(contractForm.meter_rent_eur_month),
        other_fees_eur_month: Number(contractForm.other_fees_eur_month),
        vat_rate: Number(contractForm.vat_rate),
        electricity_tax_rate: Number(contractForm.electricity_tax_rate),
        has_pepephone_discount: contractForm.has_pepephone_discount,
        bono_social_category: contractForm.bono_social_category,
        bono_social_energy_limit_kwh: Number(contractForm.bono_social_energy_limit_kwh),
        currency: 'EUR',
        billing_day: data?.contract.billing_day ?? 1,
      })
      showToast('Contrato actualizado')
      await reload()
      await onChanged()
    } catch (err) {
      setErrorLocal(err instanceof Error ? err.message : 'No se ha podido guardar el contrato')
    } finally {
      setSavingContract(false)
    }
  }

  const fetchPepe = async () => {
    setPepeError(null)
    setPepeLoading(true)
    try {
      const result = await api.fetchPepe()
      setProposal(result.proposal)
      await reloadProposals()
      showToast('Precios de Pepe detectados')
    } catch (err) {
      setPepeError(err instanceof Error ? err.message : 'No se ha podido consultar la API de Pepe')
    } finally {
      setPepeLoading(false)
    }
  }

  const confirmPepe = async () => {
    if (!proposal) return
    setConfirming(true)
    setErrorLocal(null)
    try {
      await api.confirmPepe(proposal.id)
      showToast('Precios de Pepe confirmados')
      setProposal(null)
      await reload()
      await reloadProposals()
      await onChanged()
    } catch (err) {
      setErrorLocal(err instanceof Error ? err.message : 'No se han podido confirmar los precios')
    } finally {
      setConfirming(false)
    }
  }

  const saveManual = async () => {
    if (!manual.p1_price || !manual.p2_price || !manual.p3_price) {
      setErrorLocal('Introduce al menos los precios de punta, llano y valle.')
      return
    }
    setManualSaving(true)
    setErrorLocal(null)
    try {
      await api.saveManualPrice({
        month: manual.month,
        p1_price: Number(manual.p1_price),
        p2_price: Number(manual.p2_price),
        p3_price: Number(manual.p3_price),
        power_p1_price: Number(manual.power_p1_price),
        power_p2_price: Number(manual.power_p2_price),
        service_fee_eur_month: manual.service_fee_eur_month === '' ? null : Number(manual.service_fee_eur_month),
        social_bond_eur_month: manual.social_bond_eur_month === '' ? null : Number(manual.social_bond_eur_month),
        vat_rate: manual.vat_rate === '' ? null : Number(manual.vat_rate),
        electricity_tax_rate:
          manual.electricity_tax_rate === '' ? null : Number(manual.electricity_tax_rate),
        source: 'manual',
      })
      showToast('Precios guardados')
      setManualOpen(false)
      await reload()
      await onChanged()
    } catch (err) {
      setErrorLocal(err instanceof Error ? err.message : 'No se han podido guardar los precios')
    } finally {
      setManualSaving(false)
    }
  }

  const calibrate = async () => {
    if (!calibration.actual_kwh || Number(calibration.actual_kwh) <= 0) {
      setErrorLocal('Introduce los kWh de la factura para calibrar.')
      return
    }
    setCalibrating(true)
    setErrorLocal(null)
    setCalibrationResult(null)
    try {
      const result = await api.calibrate({
        month: calibration.month,
        actual_kwh: Number(calibration.actual_kwh),
        actual_cost_eur: calibration.actual_cost_eur === '' ? null : Number(calibration.actual_cost_eur),
        notes: calibration.notes || null,
      })
      setCalibrationResult({
        factor: result.factor,
        estimated_kwh: result.estimated_kwh,
        estimated_cost: result.estimated_cost,
      })
      showToast('Calibración guardada')
      await reload()
      await reloadCalibrations()
      await onChanged()
    } catch (err) {
      setErrorLocal(err instanceof Error ? err.message : 'No se ha podido calibrar')
    } finally {
      setCalibrating(false)
    }
  }

  const saveEsios = async () => {
    setSavingEsios(true)
    setErrorLocal(null)
    try {
      await api.updateSettings({ esios_entity_id: esiosEntity || null })
      showToast('Sensor ESIOS guardado')
      await onChanged()
    } catch (err) {
      setErrorLocal(err instanceof Error ? err.message : 'No se ha podido guardar el sensor')
    } finally {
      setSavingEsios(false)
    }
  }

  if (loading && !data) return <Loading label="Cargando tarifa…" />
  if (error && !data) return <ErrorBox message={error} />
  if (!data) return null

  const price = data.price
  const fixed = data.fixed
  const latestCalibration = calibrationsData?.items?.[0]
  const esiosPriceEntities = (priceEntities?.items ?? []).filter((entity) => entity.unit === '€/kWh' || entity.unit === 'EUR/kWh')

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <div className="eyebrow">
            <BadgeEuro size={12} /> Tarifa y factura
          </div>
          <h1 className="page-title">Tu tarifa, sin letra pequeña.</h1>
          <p className="page-subtitle">
            Precios por tramo, potencia, cuotas e impuestos. Pepe publica el precio del mes pasado; la app
            lo marca como provisional hasta que se confirme.
          </p>
        </div>
        <div className="actions">
          <Button onClick={() => void reload()}>
            <RefreshCw size={14} /> Actualizar
          </Button>
          {selectedProfile?.price_source.startsWith('pepe_api') ? (
            <Button variant="primary" onClick={() => void fetchPepe()} disabled={pepeLoading}>
              <CloudDownload size={14} /> {pepeLoading ? 'Consultando…' : 'Buscar precios de Pepe'}
            </Button>
          ) : null}
        </div>
      </div>

      <div className="tabs mb-12">
        {[
          { value: 'contract' as Tab, label: 'Contrato' },
          { value: 'prices' as Tab, label: 'Precios' },
          { value: 'bill' as Tab, label: 'Factura' },
          { value: 'comparator' as Tab, label: 'Comparador' },
          { value: 'esios' as Tab, label: 'ESIOS' },
        ].map((item) => (
          <button
            key={item.value}
            type="button"
            className={`tab ${tab === item.value ? 'active' : ''}`}
            onClick={() => setTab(item.value)}
          >
            {item.label}
          </button>
        ))}
      </div>

      {errorLocal ? <ErrorBox message={errorLocal} /> : null}
      {pepeError ? (
        <Banner tone="warning">
          <Info size={15} style={{ flexShrink: 0, marginTop: 1 }} />
          <span>
            <strong>No se han podido leer los precios automáticamente.</strong> {pepeError} Puedes
            introducirlos a mano con el botón “Precios manuales”.
            <Button size="sm" variant="ghost" className="mt-8" onClick={() => setManualOpen(true)}>
              Precios manuales
            </Button>
          </span>
        </Banner>
      ) : null}

      {pendingProposals.length > 0 ? (
        <Banner tone="accent">
          <Sparkles size={15} style={{ flexShrink: 0, marginTop: 1 }} />
          <span>
            Hay <strong>{pendingProposals.length} propuesta(s) de precios pendientes</strong> de confirmar.
            <Button size="sm" variant="ghost" onClick={() => setProposal(pendingProposals[0])}>
              Revisar
            </Button>
          </span>
        </Banner>
      ) : null}

      {tab === 'contract' ? (
        <Card className="mt-12">
          <div className="card-header">
            <div>
              <h2 className="card-title">Datos del contrato</h2>
              <p className="card-subtitle">Se usan para calcular potencia, impuestos y tramos.</p>
            </div>
            <Landmark size={17} className="muted" />
          </div>
          <div className="card-body">
            <div className="form-grid">
              <Field label="Nombre">
                <Input value={contractForm.name} onChange={(event) => setContract('name', event.target.value)} />
              </Field>
              <Field
                label="Compañía y tarifa"
                hint={selectedProfile ? `${selectedProfile.notes}${selectedProfile.requires_manual_prices ? ' Precios manuales.' : ''}` : undefined}
              >
                <Select
                  value={contractForm.tariff_profile_id}
                  onChange={(event) => applyProfile(event.target.value)}
                >
                  {profiles.map((profile) => (
                    <option key={profile.id} value={profile.id}>
                      {profile.company} · {profile.name}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Potencia P1 (kW)" hint="Punta y llano">
                <Input
                  type="number"
                  step="0.01"
                  min="0"
                  value={contractForm.power_p1_kw}
                  onChange={(event) => setContract('power_p1_kw', event.target.value)}
                />
              </Field>
              <Field label="Potencia P2 (kW)" hint="Valle">
                <Input
                  type="number"
                  step="0.01"
                  min="0"
                  value={contractForm.power_p2_kw}
                  onChange={(event) => setContract('power_p2_kw', event.target.value)}
                />
              </Field>
              <Field label="Cuota de servicio (€/mes)" hint="Impuestos incluidos">
                <Input
                  type="number"
                  step="any"
                  min="0"
                  value={contractForm.service_fee_eur_month}
                  onChange={(event) => setContract('service_fee_eur_month', event.target.value)}
                />
              </Field>
              <Field label="Financiación del bono social (€/mes)" hint="Impuestos incluidos">
                <Input
                  type="number"
                  step="any"
                  min="0"
                  value={contractForm.social_bond_eur_month}
                  onChange={(event) => setContract('social_bond_eur_month', event.target.value)}
                />
              </Field>
              <Field label="Alquiler contador (€/mes)">
                <Input
                  type="number"
                  step="0.01"
                  min="0"
                  value={contractForm.meter_rent_eur_month}
                  onChange={(event) => setContract('meter_rent_eur_month', event.target.value)}
                />
              </Field>
              <Field label="Otras cuotas (€/mes)">
                <Input
                  type="number"
                  step="0.01"
                  min="0"
                  value={contractForm.other_fees_eur_month}
                  onChange={(event) => setContract('other_fees_eur_month', event.target.value)}
                />
              </Field>
              <Field label="IVA" hint="21 % por defecto">
                <Input
                  type="number"
                  step="0.01"
                  min="0"
                  max="1"
                  value={contractForm.vat_rate}
                  onChange={(event) => setContract('vat_rate', event.target.value)}
                />
              </Field>
              <Field label="Impuesto eléctrico" hint="5,113 % por defecto">
                <Input
                  type="number"
                  step="any"
                  min="0"
                  max="1"
                  value={contractForm.electricity_tax_rate}
                  onChange={(event) => setContract('electricity_tax_rate', event.target.value)}
                />
              </Field>
              <Field
                label="Festivos"
                hint="Se usan para saber cuándo todo el día es valle."
              >
                <Select value={contractForm.region} onChange={(event) => setContract('region', event.target.value)}>
                  {REGIONS.map((region) => (
                    <option key={region.value} value={region.value}>
                      {region.label}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Peaje de acceso">
                <Input value={selectedProfile?.access_toll ?? data.contract.access_toll} disabled />
              </Field>
            </div>
            {selectedProfile?.supports_pepephone_discount ? (
              <Toggle
                checked={contractForm.has_pepephone_discount}
                onChange={togglePepephone}
                label="Soy cliente de Pepephone"
                hint="La cuota de servicio pasa a 0 €/mes."
              />
            ) : null}
            <div className="form-grid mt-12">
              <Field label="Categoría de bono social" hint="Solo se aplica al PVPC.">
                <Select
                  value={contractForm.bono_social_category}
                  onChange={(event) =>
                    setContract('bono_social_category', event.target.value as BonoSocialCategory)
                  }
                >
                  <option value="none">No soy beneficiario</option>
                  <option value="vulnerable">Vulnerable · 42,5 %</option>
                  <option value="severe">Vulnerable severo · 57,5 %</option>
                  <option value="exclusion">Riesgo de exclusión · 100 %</option>
                </Select>
              </Field>
              <Field label="Límite anual de energía">
                <Select
                  value={contractForm.bono_social_energy_limit_kwh}
                  onChange={(event) =>
                    setContract('bono_social_energy_limit_kwh', event.target.value)
                  }
                >
                  {BONO_LIMITS.map((limit) => (
                    <option key={limit.value} value={limit.value}>
                      {limit.label}
                    </option>
                  ))}
                </Select>
              </Field>
            </div>
            {contractForm.bono_social_category !== 'none' && selectedProfile && !selectedProfile.bono_social_eligible ? (
              <Banner tone="warning">
                <Info size={15} style={{ flexShrink: 0, marginTop: 1 }} />
                <span>
                  El descuento del bono social solo se aplica al PVPC. Con esta tarifa no se aplicará;
                  puedes usar el comparador para ver PVPC con el descuento.
                </span>
              </Banner>
            ) : null}
            <div className="between mt-16">
              <span className="small muted">
                {selectedProfile
                  ? `${selectedProfile.company} · ${selectedProfile.name} · ${selectedProfile.access_toll}`
                  : data.contract.tariff_type}
              </span>
              <Button variant="primary" onClick={() => void saveContract()} disabled={savingContract}>
                <Save size={14} /> {savingContract ? 'Guardando…' : 'Guardar contrato'}
              </Button>
            </div>
          </div>
        </Card>
      ) : null}

      {tab === 'prices' ? (
        <div className="card-grid mt-12">
          <Card className="span-7">
            <div className="card-header">
              <div>
                <h2 className="card-title">Precios del mes</h2>
                <p className="card-subtitle">
                  {price
                    ? `Precios de ${price.month_label}${price.is_fallback ? ' usados como provisionales' : ''}.`
                    : 'Todavía no hay precios confirmados.'}
                </p>
              </div>
              <Badge tone={price ? (price.is_fallback ? 'yellow' : 'green') : 'red'}>
                {price ? (price.is_fallback ? 'Provisional' : 'Confirmado') : 'Sin precio'}
              </Badge>
            </div>
            <div className="card-body">
              {price ? (
                <>
                  {price.is_fallback ? (
                    <Banner tone="warning">
                      <CalendarDays size={14} style={{ flexShrink: 0, marginTop: 1 }} />
                      <span>
                        Pepe publica el precio del mes pasado. {price.month_label} se usa como referencia
                        provisional para {data.month_label}. Cuando publiquen el mes actual, confírmalo.
                      </span>
                    </Banner>
                  ) : null}
                  {price.is_hourly ? (
                    <Banner tone="accent">
                      <Zap size={14} style={{ flexShrink: 0, marginTop: 1 }} />
                      <span>
                        <strong>PVPC horario.</strong> Las tarjetas muestran la media de cada tramo. El coste
                        real se calcula hora a hora con los precios de REE. Consulta la curva en Horarios.
                      </span>
                    </Banner>
                  ) : null}
                  <div className="period-grid mt-12">
                    {price.periods.map((period) => (
                      <div className="period-card" key={period.id}>
                        <div className="period-name">
                          <span
                            className="period-dot"
                            style={{
                              background:
                                period.id === 'P1'
                                  ? 'var(--p1)'
                                  : period.id === 'P2'
                                    ? 'var(--p2)'
                                    : 'var(--p3)',
                            }}
                          />
                          {period.name}
                        </div>
                        <div className="period-cost" style={{ fontSize: 18 }}>
                          {pricePerKwh(period.price)}
                        </div>
                        <div className="period-price">Energía sin impuestos</div>
                      </div>
                    ))}
                  </div>
                  <div className="form-grid-3 mt-16">
                    <div>
                      <div className="field-label">Potencia P1</div>
                      <div className="mono">{pricePerKwDay(price.power_p1_price)}</div>
                      <div className="field-hint">Sin impuestos</div>
                    </div>
                    <div>
                      <div className="field-label">Potencia P2</div>
                      <div className="mono">{pricePerKwDay(price.power_p2_price)}</div>
                      <div className="field-hint">Sin impuestos</div>
                    </div>
                    <div>
                      <div className="field-label">Fuente</div>
                      <div>
                        {price.source === 'pepe_api'
                          ? 'API pública de Pepe'
                          : price.source === 'ree_pvpc'
                            ? 'REE · PVPC horario'
                            : 'Manual'}
                      </div>
                      <div className="field-hint">{formatDate(price.valid_from)}</div>
                    </div>
                  </div>
                  <div className="between mt-16">
                    <span className="small muted">
                      Precios de {formatDate(price.valid_from)} ·{' '}
                      {price.status === 'confirmed' ? 'confirmados' : price.status}
                    </span>
                    <div className="flex gap-8">
                      {selectedProfile?.price_source.startsWith('pepe_api') ? (
                        <>
                          <Button size="sm" variant="ghost" onClick={() => setManualOpen(true)}>
                            Precios manuales
                          </Button>
                          <Button size="sm" onClick={() => void fetchPepe()} disabled={pepeLoading}>
                            <CloudDownload size={13} /> Actualizar desde Pepe
                          </Button>
                        </>
                      ) : selectedProfile?.price_source === 'ree_pvpc' ? (
                        <Button size="sm" variant="ghost" onClick={() => void reload()}>
                          <RefreshCw size={13} /> Actualizar PVPC
                        </Button>
                      ) : (
                        <Button size="sm" variant="ghost" onClick={() => setManualOpen(true)}>
                          Precios manuales
                        </Button>
                      )}
                    </div>
                  </div>
                </>
              ) : (
                <div className="empty" style={{ padding: '28px 10px' }}>
                  <div className="empty-icon">
                    <BadgeEuro size={22} />
                  </div>
                  <div className="empty-title">Añade los precios de tu tarifa</div>
                  <div className="empty-text">
                    {selectedProfile?.price_source === 'ree_pvpc'
                      ? 'El PVPC se descarga de la API pública de REE. Pulsa actualizar para cargar los precios horarios.'
                      : 'Puedes leerlos automáticamente de Pepe o introducirlos a mano. Sin precios no se puede calcular el coste.'}
                  </div>
                  <div className="flex gap-8 mt-12">
                    {selectedProfile?.price_source.startsWith('pepe_api') ? (
                      <Button variant="primary" onClick={() => void fetchPepe()} disabled={pepeLoading}>
                        <CloudDownload size={14} /> {pepeLoading ? 'Consultando…' : 'Buscar en Pepe'}
                      </Button>
                    ) : null}
                    {selectedProfile?.price_source !== 'ree_pvpc' ? (
                      <Button onClick={() => setManualOpen(true)}>Introducir manualmente</Button>
                    ) : (
                      <Button variant="primary" onClick={() => void reload()}>
                        <RefreshCw size={14} /> Cargar PVPC
                      </Button>
                    )}
                  </div>
                </div>
              )}
            </div>
          </Card>

          <Card className="span-5">
            <div className="card-header">
              <div>
                <h2 className="card-title">
                  {selectedProfile?.price_source === 'ree_pvpc'
                    ? 'Cómo funciona PVPC'
                    : selectedProfile?.price_source.startsWith('pepe_api')
                      ? 'Cómo funciona Pepe'
                      : 'Precios manuales'}
                </h2>
                <p className="card-subtitle">
                  {selectedProfile?.price_source === 'ree_pvpc'
                    ? 'Precio horario y bono social.'
                    : selectedProfile?.price_source.startsWith('pepe_api')
                      ? 'Precio mensual por tramo, no PVPC horario.'
                      : 'Perfil de mercado libre; confirma los precios con tu factura.'}
                </p>
              </div>
              <Link2 size={16} className="muted" />
            </div>
            <div className="card-body">
              <div className="small muted" style={{ lineHeight: 1.65 }}>
                {selectedProfile?.price_source === 'ree_pvpc'
                  ? 'El PVPC se calcula hora a hora con los precios publicados por REE. El término de potencia es regulado y el bono social solo se aplica a esta tarifa. La factura se calcula con la curva horaria de tu consumo.'
                  : selectedProfile?.price_source.startsWith('pepe_api')
                    ? 'La Tarifa Variable de Pepe publica un precio distinto para punta, llano y valle cada mes. Dentro de un tramo, el precio no cambia hora a hora. Por eso tu factura se calcula con estos precios mensuales y el calendario 2.0TD, no con el precio horario de ESIOS.'
                    : 'Los precios de las comercializadoras de mercado libre dependen de tu contrato y no tienen una API pública fiable. Este perfil se rellena a mano y se puede actualizar cuando cambie tu tarifa.'}
              </div>
              <div className="banner mt-12">
                <Info size={14} style={{ flexShrink: 0, marginTop: 1 }} />
                <span>
                  {selectedProfile?.price_source === 'ree_pvpc'
                    ? 'El descuento del bono social solo se aplica a PVPC. La financiación regulada aparece como línea independiente.'
                    : selectedProfile?.price_source.startsWith('pepe_api')
                      ? 'Pepe suele publicar el precio del mes anterior. La app lo marca como provisional y usa el último disponible hasta que confirmes el mes actual.'
                      : 'Los perfiles del catálogo comunitario son orientativos. Confirma siempre la cuota, los precios y los impuestos con tu factura.'}
                </span>
              </div>
              <Button
                variant="ghost"
                size="sm"
                className="mt-12"
                onClick={() =>
                  window.open(
                    selectedProfile?.price_source === 'ree_pvpc'
                      ? 'https://www.esios.ree.es/es/pvpc'
                      : selectedProfile?.source_url ||
                          'https://www.pepeenergy.com/tarifas-luz/tarifa-variable-luz',
                    '_blank',
                    'noopener,noreferrer',
                  )
                }
              >
                Ver fuente <ExternalLink size={12} />
              </Button>
            </div>
          </Card>
        </div>
      ) : null}

      {tab === 'bill' ? (
        <div className="card-grid mt-12">
          <Card className="span-7">
            <div className="card-header">
              <div>
                <h2 className="card-title">Factura estimada</h2>
                <p className="card-subtitle">{data.month_label} · {data.days} días</p>
              </div>
              <Coins size={17} className="muted" />
            </div>
            <div className="card-body">
              {fixed ? (
                <>
                  <div className="between" style={{ fontSize: 13 }}>
                    <span>Energía</span>
                    <span className="mono">{eur(fixed.energy_cost)}</span>
                  </div>
                  <div className="between small muted mt-8">
                    <span>Potencia contratada</span>
                    <span className="mono">{eur(fixed.power_cost)}</span>
                  </div>
                  <div className="between small muted mt-8">
                    <span>Cuota de servicio</span>
                    <span className="mono">{eur(fixed.service_fee)}</span>
                  </div>
                  {fixed.service_discount && fixed.service_discount > 0 ? (
                    <div className="between small mt-8" style={{ color: 'var(--success)' }}>
                      <span>Descuento Pepephone</span>
                      <span className="mono">−{eur(fixed.service_discount)}</span>
                    </div>
                  ) : null}
                  <div className="between small muted mt-8">
                    <span>Financiación del bono social</span>
                    <span className="mono">{eur(fixed.social_bond)}</span>
                  </div>
                  {fixed.bono_social_discount && fixed.bono_social_discount > 0 ? (
                    <div className="between small mt-8" style={{ color: 'var(--success)' }}>
                      <span>
                        Descuento bono social
                        {fixed.bono_social_percentage
                          ? ` (${(fixed.bono_social_percentage * 100).toFixed(1)} %)`
                          : ''}
                      </span>
                      <span className="mono">−{eur(fixed.bono_social_discount)}</span>
                    </div>
                  ) : null}
                  <div className="between small muted mt-8">
                    <span>Alquiler de contador</span>
                    <span className="mono">{eur(fixed.meter_rent)}</span>
                  </div>
                  <div className="between small muted mt-8">
                    <span>Otras cuotas</span>
                    <span className="mono">{eur(fixed.other_fees)}</span>
                  </div>
                  <div className="between small muted mt-8">
                    <span>Impuesto eléctrico ({(fixed.electricity_tax_rate * 100).toFixed(3)} %)</span>
                    <span className="mono">{eur(fixed.electricity_tax)}</span>
                  </div>
                  <div className="between small muted mt-8">
                    <span>IVA ({(fixed.vat_rate * 100).toFixed(0)} %)</span>
                    <span className="mono">{eur(fixed.vat)}</span>
                  </div>
                  <div
                    className="between mt-16"
                    style={{ paddingTop: 14, borderTop: '1px solid var(--border)', fontSize: 18, fontWeight: 750 }}
                  >
                    <span>Total</span>
                    <span className="mono">{eur(fixed.total)}</span>
                  </div>
                  <div className="small muted mt-8">
                    Estimación del mes actual. La factura real puede variar por lecturas, ajustes o cambios
                    de precio.
                  </div>
                  {data.contract.bono_social_category !== 'none' &&
                  selectedProfile &&
                  !selectedProfile.bono_social_eligible ? (
                    <Banner tone="warning">
                      <Info size={14} style={{ flexShrink: 0, marginTop: 1 }} />
                      <span>
                        El descuento del bono social solo se aplica al PVPC. Con esta tarifa no se ha
                        aplicado; el comparador muestra cuánto ahorrarías con PVPC.
                      </span>
                    </Banner>
                  ) : null}
                </>
              ) : (
                <Banner tone="warning">
                  <Info size={15} style={{ flexShrink: 0, marginTop: 1 }} />
                  <span>Confirma los precios de tu tarifa para calcular la factura.</span>
                </Banner>
              )}
            </div>
          </Card>

          <Card className="span-5">
            <div className="card-header">
              <div>
                <h2 className="card-title">Calibrar con factura</h2>
                <p className="card-subtitle">Ajusta la estimación a tu consumo real.</p>
              </div>
              <Gauge size={17} className="muted" />
            </div>
            <div className="card-body">
              <div className="form-grid">
                <Field label="Mes de la factura">
                  <Input
                    type="month"
                    value={calibration.month}
                    onChange={(event) => setCalibration((current) => ({ ...current, month: event.target.value }))}
                  />
                </Field>
                <Field label="kWh consumidos">
                  <Input
                    type="number"
                    min="0"
                    step="0.1"
                    value={calibration.actual_kwh}
                    onChange={(event) =>
                      setCalibration((current) => ({ ...current, actual_kwh: event.target.value }))
                    }
                    placeholder="Ej. 320"
                  />
                </Field>
              </div>
              <Field label="Importe total de la factura (€)" hint="Opcional, para comparar">
                <Input
                  type="number"
                  min="0"
                  step="0.01"
                  value={calibration.actual_cost_eur}
                  onChange={(event) =>
                    setCalibration((current) => ({ ...current, actual_cost_eur: event.target.value }))
                  }
                  placeholder="Ej. 92,40"
                />
              </Field>
              <Button variant="primary" className="mt-12" onClick={() => void calibrate()} disabled={calibrating}>
                <Gauge size={14} /> {calibrating ? 'Calibrando…' : 'Calibrar estimación'}
              </Button>
              {calibrationResult ? (
                <div className="banner accent mt-12">
                  <Check size={15} style={{ flexShrink: 0, marginTop: 1 }} />
                  <span>
                    Factor <strong>{calibrationResult.factor.toFixed(2)}</strong>. Estimado{' '}
                    {calibrationResult.estimated_kwh.toFixed(1)} kWh → factura real{' '}
                    {calibration.actual_kwh} kWh. La estimación de los aparatos se ajusta con ese factor.
                  </span>
                </div>
              ) : null}
              <div className="small muted mt-12">
                Factor actual: <strong>{data.calibration_factor.toFixed(2)}</strong>
                {latestCalibration ? ` · última calibración ${formatDate(latestCalibration.created_at)}` : ' · sin calibrar'}
              </div>
            </div>
          </Card>
        </div>
      ) : null}

      {tab === 'comparator' ? (
        <div className="card-grid mt-12">
          <Card className="span-12">
            <div className="card-header">
              <div>
                <h2 className="card-title">Comparador Pepe vs PVPC</h2>
                <p className="card-subtitle">
                  Mismo consumo estimado y misma potencia contratada. Recomendamos un mes completo; la
                  comparación es orientativa.
                </p>
              </div>
              <div className="flex gap-8" style={{ alignItems: 'center' }}>
                <Input
                  type="month"
                  value={comparatorMonth}
                  onChange={(event) => setComparatorMonth(event.target.value || comparatorMonth)}
                  style={{ width: 155 }}
                  aria-label="Mes del comparador"
                />
                <Button size="sm" onClick={() => void reloadComparator()} disabled={comparatorLoading}>
                  <RefreshCw size={13} /> Actualizar
                </Button>
              </div>
            </div>
            <div className="card-body">
              {comparatorLoading && !comparatorData ? (
                <Loading label="Calculando comparación…" />
              ) : comparatorError && !comparatorData ? (
                <Banner tone="warning">
                  <Info size={15} style={{ flexShrink: 0, marginTop: 1 }} />
                  <span>{comparatorError}</span>
                </Banner>
              ) : comparatorData ? (
                <>
                  <div className="period-grid">
                    <div className="period-card">
                      <div className="field-label">Tu tarifa actual</div>
                      <div className="period-cost" style={{ fontSize: 24 }}>
                        {eur(comparatorData.current_total)}
                      </div>
                      <div className="period-energy">{comparatorData.current_label}</div>
                      <div className="period-price">
                        Energía: {eur(comparatorData.current_energy_cost)}
                      </div>
                    </div>
                    <div className="period-card">
                      <div className="field-label">Alternativa</div>
                      <div className="period-cost" style={{ fontSize: 24 }}>
                        {eur(comparatorData.alternative_total)}
                      </div>
                      <div className="period-energy">{comparatorData.alternative_label}</div>
                      <div className="period-price">
                        Energía: {eur(comparatorData.alternative_energy_cost)}
                      </div>
                    </div>
                    <div className={`period-card ${comparatorData.savings_eur_month > 0 ? 'comparison-win' : ''}`}>
                      <div className="field-label">
                        {comparatorData.savings_eur_month > 0 ? 'Ahorro potencial' : 'Diferencia'}
                      </div>
                      <div
                        className="period-cost"
                        style={{
                          fontSize: 24,
                          color:
                            comparatorData.savings_eur_month > 0
                              ? 'var(--success)'
                              : 'var(--text)',
                        }}
                      >
                        {eur(Math.abs(comparatorData.savings_eur_month))}
                      </div>
                      <div className="period-energy">
                        {comparatorData.savings_eur_month > 0
                          ? `más barato con ${comparatorData.alternative_label}`
                          : 'tu tarifa actual es más barata'}
                      </div>
                    </div>
                  </div>
                  {comparatorData.missing_hours > 0 && comparatorData.pvpc_coverage < 0.95 ? (
                    <Banner tone="warning">
                      <Info size={15} style={{ flexShrink: 0, marginTop: 1 }} />
                      <span>
                        Faltan {comparatorData.missing_hours} horas de PVPC para el mes. Se ha usado el
                        precio medio disponible; la comparación puede cambiar.
                      </span>
                    </Banner>
                  ) : null}
                  <div className="mt-12 small muted">
                    {comparatorData.notes.map((note) => (
                      <div key={note}>· {note}</div>
                    ))}
                  </div>
                  {comparatorData.current_bono_social > 0 || comparatorData.alternative_bono_social > 0 ? (
                    <div className="banner mt-12">
                      <Info size={14} style={{ flexShrink: 0, marginTop: 1 }} />
                      <span>
                        Bono social aplicado: actual{' '}
                        {eur(comparatorData.current_bono_social)} · alternativa{' '}
                        {eur(comparatorData.alternative_bono_social)}. Solo se aplica a PVPC.
                      </span>
                    </div>
                  ) : null}
                </>
              ) : null}
            </div>
          </Card>
        </div>
      ) : null}

      {tab === 'esios' ? (
        <Card className="mt-12">
          <div className="card-header">
            <div>
              <h2 className="card-title">Referencia de mercado ESIOS</h2>
              <p className="card-subtitle">Opcional. No se aplica a la factura de Pepe.</p>
            </div>
            <Zap size={17} className="muted" />
          </div>
          <div className="card-body">
            <div className="banner">
              <Info size={15} style={{ flexShrink: 0, marginTop: 1 }} />
              <span>
                Conecta ESIOS sirve para ver el precio horario del mercado/PVPC. La Tarifa Variable de Pepe
                usa precios mensuales por tramo; por eso no se mezclan. El comparador Pepe vs PVPC llegará en
                la fase 2.
              </span>
            </div>
            {priceEntities?.configured ? (
              <>
                <Field label="Sensor de precio de Home Assistant" hint="Entidades con unidad €/kWh.">
                  <Select value={esiosEntity} onChange={(event) => setEsiosEntity(event.target.value)}>
                    <option value="">Sin sensor</option>
                    {esiosPriceEntities.map((entity) => (
                      <option value={entity.entity_id} key={entity.entity_id}>
                        {entity.name} · {entity.entity_id} ({entity.state} {entity.unit})
                      </option>
                    ))}
                  </Select>
                </Field>
                {esiosPriceEntities.length === 0 ? (
                  <div className="small muted mt-8">
                    No se han encontrado sensores de precio. Comprueba que Conecta ESIOS expone una entidad
                    con unidad €/kWh.
                  </div>
                ) : null}
                <Button className="mt-12" onClick={() => void saveEsios()} disabled={savingEsios}>
                  <Save size={14} /> {savingEsios ? 'Guardando…' : 'Guardar sensor'}
                </Button>
              </>
            ) : (
              <div className="empty" style={{ padding: '24px 10px' }}>
                <div className="empty-icon">
                  <Link2 size={21} />
                </div>
                <div className="empty-title">Home Assistant no está conectado</div>
                <div className="empty-text">
                  La app funciona sin HA. Si configuras la app dentro de Home Assistant, podrás elegir el
                  sensor de Conecta ESIOS aquí.
                </div>
              </div>
            )}
          </div>
        </Card>
      ) : null}

      <Modal
        open={manualOpen}
        onClose={() => setManualOpen(false)}
        title="Precios manuales"
        subtitle="Si la API de Pepe no está disponible, introduce los precios publicados."
        size="lg"
        footer={
          <>
            <Button onClick={() => setManualOpen(false)}>Cancelar</Button>
            <Button variant="primary" onClick={() => void saveManual()} disabled={manualSaving}>
              <Save size={14} /> {manualSaving ? 'Guardando…' : 'Guardar precios'}
            </Button>
          </>
        }
      >
        <div className="form-grid">
          <Field label="Mes" hint="Mes al que aplican los precios">
            <Input
              type="month"
              value={manual.month}
              onChange={(event) => setManual((current) => ({ ...current, month: event.target.value }))}
            />
          </Field>
          <Field label="Fuente">
            <Input value="Manual" disabled />
          </Field>
          <Field label="Punta (€/kWh)" hint="Sin impuestos">
            <Input
              type="number"
              step="any"
              min="0"
              value={manual.p1_price}
              onChange={(event) => setManual((current) => ({ ...current, p1_price: event.target.value }))}
            />
          </Field>
          <Field label="Llano (€/kWh)" hint="Sin impuestos">
            <Input
              type="number"
              step="any"
              min="0"
              value={manual.p2_price}
              onChange={(event) => setManual((current) => ({ ...current, p2_price: event.target.value }))}
            />
          </Field>
          <Field label="Valle (€/kWh)" hint="Sin impuestos">
            <Input
              type="number"
              step="any"
              min="0"
              value={manual.p3_price}
              onChange={(event) => setManual((current) => ({ ...current, p3_price: event.target.value }))}
            />
          </Field>
          <Field label="Potencia P1 (€/kW/día)" hint="Sin impuestos">
            <Input
              type="number"
              step="any"
              min="0"
              value={manual.power_p1_price}
              onChange={(event) =>
                setManual((current) => ({ ...current, power_p1_price: event.target.value }))
              }
            />
          </Field>
          <Field label="Potencia P2 (€/kW/día)" hint="Sin impuestos">
            <Input
              type="number"
              step="any"
              min="0"
              value={manual.power_p2_price}
              onChange={(event) =>
                setManual((current) => ({ ...current, power_p2_price: event.target.value }))
              }
            />
          </Field>
          <Field label="Cuota de servicio (€/mes)" hint="Impuestos incluidos">
            <Input
              type="number"
              step="any"
              min="0"
              value={manual.service_fee_eur_month}
              onChange={(event) =>
                setManual((current) => ({ ...current, service_fee_eur_month: event.target.value }))
              }
            />
          </Field>
          <Field label="Bono social (€/mes)" hint="Impuestos incluidos">
            <Input
              type="number"
              step="any"
              min="0"
              value={manual.social_bond_eur_month}
              onChange={(event) =>
                setManual((current) => ({ ...current, social_bond_eur_month: event.target.value }))
              }
            />
          </Field>
          <Field label="IVA">
            <Input
              type="number"
              step="0.01"
              min="0"
              max="1"
              value={manual.vat_rate}
              onChange={(event) => setManual((current) => ({ ...current, vat_rate: event.target.value }))}
            />
          </Field>
          <Field label="Impuesto eléctrico">
            <Input
              type="number"
              step="any"
              min="0"
              max="1"
              value={manual.electricity_tax_rate}
              onChange={(event) =>
                setManual((current) => ({ ...current, electricity_tax_rate: event.target.value }))
              }
            />
          </Field>
        </div>
        <div className="banner mt-12">
          <Info size={14} style={{ flexShrink: 0, marginTop: 1 }} />
          <span>
            Introduce los precios <strong>sin impuestos</strong>. La app aplica IVA e impuesto eléctrico
            por separado. Pepe publica el precio del mes pasado; puedes crear una versión por mes.
          </span>
        </div>
      </Modal>

      <Modal
        open={proposal !== null}
        onClose={() => setProposal(null)}
        title="Precios detectados en Pepe"
        subtitle={proposal ? `Publicados para ${proposal.month_label}` : undefined}
        footer={
          <>
            <Button onClick={() => setProposal(null)}>Cancelar</Button>
            <Button variant="primary" onClick={() => void confirmPepe()} disabled={confirming}>
              <Check size={14} /> {confirming ? 'Confirmando…' : 'Confirmar precios'}
            </Button>
          </>
        }
      >
        {proposal ? (
          <>
            <div className="period-grid">
              {[
                { label: 'Punta', value: proposal.p1_price },
                { label: 'Llano', value: proposal.p2_price },
                { label: 'Valle', value: proposal.p3_price },
              ].map((item) => (
                <div className="period-card" key={item.label}>
                  <div className="period-name">{item.label}</div>
                  <div className="period-cost" style={{ fontSize: 18 }}>
                    {pricePerKwh(item.value)}
                  </div>
                  <div className="period-price">Energía sin impuestos</div>
                </div>
              ))}
            </div>
            <div className="form-grid mt-12">
              <div>
                <div className="field-label">Potencia P1</div>
                <div className="mono">{pricePerKwDay(proposal.power_p1_price)}</div>
              </div>
              <div>
                <div className="field-label">Potencia P2</div>
                <div className="mono">{pricePerKwDay(proposal.power_p2_price)}</div>
              </div>
              <div>
                <div className="field-label">Cuota de servicio</div>
                <div className="mono">{eur(proposal.service_fee_eur_month)}/mes</div>
              </div>
              <div>
                <div className="field-label">Consultado</div>
                <div>{formatDateTime(proposal.fetched_at)}</div>
              </div>
            </div>
            <div className="banner mt-12">
              <ExternalLink size={14} style={{ flexShrink: 0, marginTop: 1 }} />
              <span>
                <strong>Fuente:</strong> API pública de Pepe Energy, la misma que usa su web para
                publicar los precios del último mes. Nada se aplica hasta que confirmes la propuesta.
              </span>
            </div>
            <div className="flex gap-8 mt-8" style={{ flexWrap: 'wrap' }}>
              {selectedProfile?.source_url ? (
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() =>
                    window.open(selectedProfile.source_url, '_blank', 'noopener,noreferrer')
                  }
                >
                  Ver tarifa en Pepe <ExternalLink size={12} />
                </Button>
              ) : null}
              {selectedProfile?.price_api_url ? (
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() =>
                    window.open(selectedProfile.price_api_url, '_blank', 'noopener,noreferrer')
                  }
                >
                  Ver API de Pepe <ExternalLink size={12} />
                </Button>
              ) : null}
            </div>
            <div className="banner mt-12">
              <Info size={14} style={{ flexShrink: 0, marginTop: 1 }} />
              <span>
                Se aplicarán al mes <strong>{proposal.month_label}</strong>. Si ese mes ya pasó, se usarán
                como referencia provisional para el mes actual hasta que Pepe publique el precio
                correspondiente.
              </span>
            </div>
          </>
        ) : null}
      </Modal>
    </div>
  )
}
