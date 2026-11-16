import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useId,
  useMemo,
  useState,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from 'react'
import { createPortal } from 'react-dom'
import { AlertCircle, CheckCircle2, Info, X } from 'lucide-react'
import { cn, PERIOD_COLORS, PERIOD_LABELS } from '../lib/format'
import type { PeriodId } from '../types'

/* ------------------------------------------------------------------ toasts */

type ToastType = 'success' | 'error' | 'info'
type ToastItem = { id: number; message: string; type: ToastType }
type ToastContextValue = { showToast: (message: string, type?: ToastType) => void }

const ToastContext = createContext<ToastContextValue | null>(null)

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([])

  const showToast = useCallback((message: string, type: ToastType = 'success') => {
    const id = Date.now() + Math.round(Math.random() * 1000)
    setItems((current) => [...current, { id, message, type }])
    window.setTimeout(() => {
      setItems((current) => current.filter((item) => item.id !== id))
    }, 4600)
  }, [])

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <div className="toast-stack">
        {items.map((item) => (
          <div key={item.id} className={cn('toast', item.type)}>
            {item.type === 'success' ? (
              <CheckCircle2 size={16} style={{ color: 'var(--success)', flexShrink: 0 }} />
            ) : item.type === 'error' ? (
              <AlertCircle size={16} style={{ color: 'var(--danger)', flexShrink: 0 }} />
            ) : (
              <Info size={16} style={{ color: 'var(--blue)', flexShrink: 0 }} />
            )}
            <span>{item.message}</span>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const value = useContext(ToastContext)
  if (!value) throw new Error('useToast debe usarse dentro de ToastProvider')
  return value
}

/* ------------------------------------------------------------------ basics */

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  size?: 'sm' | 'md'
}

export function Button({ variant = 'secondary', size = 'md', className, ...props }: ButtonProps) {
  return (
    <button
      className={cn(
        'btn',
        variant === 'primary' && 'btn-primary',
        variant === 'secondary' && 'btn-secondary',
        variant === 'ghost' && 'btn-ghost',
        variant === 'danger' && 'btn-danger',
        size === 'sm' && 'btn-sm',
        className,
      )}
      {...props}
    />
  )
}

export function Card({
  children,
  className,
  ...props
}: { children: ReactNode; className?: string } & React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn('card', className)} {...props}>
      {children}
    </div>
  )
}

export function Badge({
  children,
  tone = 'neutral',
  className,
}: {
  children: ReactNode
  tone?: 'green' | 'yellow' | 'red' | 'blue' | 'neutral' | 'accent'
  className?: string
}) {
  return <span className={cn('badge', `badge-${tone}`, className)}>{children}</span>
}

export function Stat({
  label,
  value,
  meta,
  icon,
}: {
  label: string
  value: ReactNode
  meta?: ReactNode
  icon?: ReactNode
}) {
  return (
    <div className="stat">
      <div className="stat-top">
        <span>{label}</span>
        {icon ? <span className="stat-icon">{icon}</span> : null}
      </div>
      <div className="stat-value">{value}</div>
      {meta ? <div className="stat-meta">{meta}</div> : null}
    </div>
  )
}

export function Progress({ value, slim = false }: { value: number; slim?: boolean }) {
  return (
    <div className={cn('progress', slim && 'slim')}>
      <span style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
    </div>
  )
}

export function Tabs<T extends string>({
  value,
  options,
  onChange,
}: {
  value: T
  options: Array<{ value: T; label: string }>
  onChange: (value: T) => void
}) {
  return (
    <div className="tabs">
      {options.map((option) => (
        <button
          key={option.value}
          className={cn('tab', option.value === value && 'active')}
          onClick={() => onChange(option.value)}
          type="button"
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}

/* ------------------------------------------------------------------ forms */

export function Field({
  label,
  hint,
  children,
  className,
}: {
  label: string
  hint?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <label className={cn('field', className)}>
      <span className="field-label">{label}</span>
      {children}
      {hint ? <span className="field-hint">{hint}</span> : null}
    </label>
  )
}

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cn('input', props.className)} {...props} />
}

export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className={cn('select', props.className)} {...props} />
}

export function Textarea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={cn('textarea', props.className)} {...props} />
}

export function Toggle({
  checked,
  onChange,
  label,
  hint,
}: {
  checked: boolean
  onChange: (value: boolean) => void
  label: string
  hint?: string
}) {
  return (
    <div className="toggle-row">
      <div>
        <div style={{ fontSize: 12.5, fontWeight: 650 }}>{label}</div>
        {hint ? <div className="field-hint">{hint}</div> : null}
      </div>
      <button
        type="button"
        className={cn('toggle', checked && 'on')}
        onClick={() => onChange(!checked)}
        aria-pressed={checked}
        aria-label={label}
      />
    </div>
  )
}

export function Segmented<T extends string>({
  value,
  onChange,
  options,
  columns = 4,
}: {
  value: T
  onChange: (value: T) => void
  options: Array<{ value: T; label: string; icon?: ReactNode }>
  columns?: 2 | 4
}) {
  return (
    <div className={cn('segmented', columns === 4 && 'cols-4')}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          className={cn('segment', option.value === value && 'active')}
          onClick={() => onChange(option.value)}
        >
          {option.icon}
          {option.label}
        </button>
      ))}
    </div>
  )
}

/* ------------------------------------------------------------------ modal */

export function Modal({
  open,
  onClose,
  title,
  subtitle,
  children,
  footer,
  size = 'md',
}: {
  open: boolean
  onClose: () => void
  title: string
  subtitle?: string
  children: ReactNode
  footer?: ReactNode
  size?: 'sm' | 'md' | 'lg'
}) {
  const titleId = useId()

  useEffect(() => {
    if (!open) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = previous
    }
  }, [open, onClose])

  if (!open) return null

  return createPortal(
    <div
      className="modal-overlay"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <div
        className={cn('modal', size === 'sm' && 'narrow', size === 'lg' && 'wide')}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
      >
        <div className="modal-header">
          <div>
            <h2 className="modal-title" id={titleId}>
              {title}
            </h2>
            {subtitle ? <p className="modal-subtitle">{subtitle}</p> : null}
          </div>
          <button className="icon-button" type="button" onClick={onClose} aria-label="Cerrar">
            <X size={16} />
          </button>
        </div>
        <div className="modal-body">{children}</div>
        {footer ? <div className="modal-footer">{footer}</div> : null}
      </div>
    </div>,
    document.body,
  )
}

/* ------------------------------------------------------------------ misc */

export function EmptyState({
  icon,
  title,
  text,
  action,
}: {
  icon?: ReactNode
  title: string
  text: string
  action?: ReactNode
}) {
  return (
    <div className="empty">
      <div className="empty-icon">{icon ?? <Info size={22} />}</div>
      <div className="empty-title">{title}</div>
      <div className="empty-text">{text}</div>
      {action ? <div className="mt-12">{action}</div> : null}
    </div>
  )
}

export function Loading({ label = 'Cargando…' }: { label?: string }) {
  return (
    <div className="loading">
      <div className="spinner" />
      <div className="small muted">{label}</div>
    </div>
  )
}

export function ErrorBox({ message }: { message: string }) {
  return <div className="error-box">{message}</div>
}

export function Banner({
  children,
  tone = 'default',
}: {
  children: ReactNode
  tone?: 'default' | 'warning' | 'accent'
}) {
  return <div className={cn('banner', tone !== 'default' && tone)}>{children}</div>
}

export function QualityRing({ score, label }: { score: number; label: string }) {
  const radius = 34
  const circumference = 2 * Math.PI * radius
  const offset = circumference * (1 - Math.max(0, Math.min(100, score)) / 100)
  const color = score >= 80 ? 'var(--success)' : score >= 55 ? 'var(--warning)' : 'var(--danger)'
  return (
    <div className="quality-ring" title={`${label} · ${score}%`}>
      <svg width="84" height="84" viewBox="0 0 84 84" aria-hidden="true">
        <circle cx="42" cy="42" r={radius} fill="none" stroke="var(--surface-3)" strokeWidth="6" />
        <circle
          cx="42"
          cy="42"
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth="6"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
        />
      </svg>
      <div className="quality-ring-label">{Math.round(score)}%</div>
    </div>
  )
}

export function PeriodBar({
  values,
  height = 6,
}: {
  values: Record<PeriodId, number>
  height?: number
}) {
  const total = (values.P1 ?? 0) + (values.P2 ?? 0) + (values.P3 ?? 0)
  if (total <= 0) {
    return <div className="progress" style={{ height }} />
  }
  return (
    <div
      style={{
        display: 'flex',
        height,
        borderRadius: 99,
        overflow: 'hidden',
        background: 'var(--surface-3)',
      }}
      title={`Punta ${Math.round((values.P1 / total) * 100)}% · Llano ${Math.round(
        (values.P2 / total) * 100,
      )}% · Valle ${Math.round((values.P3 / total) * 100)}%`}
    >
      {(['P1', 'P2', 'P3'] as PeriodId[]).map((period) => (
        <span
          key={period}
          style={{
            display: 'block',
            width: `${(values[period] / total) * 100}%`,
            background: PERIOD_COLORS[period],
          }}
        />
      ))}
    </div>
  )
}

export function PeriodLegend() {
  return (
    <div className="legend">
      {(['P1', 'P2', 'P3'] as PeriodId[]).map((period) => (
        <div key={period} className="legend-item">
          <span
            style={{
              width: 7,
              height: 7,
              borderRadius: 99,
              background: PERIOD_COLORS[period],
              display: 'inline-block',
            }}
          />
          {PERIOD_LABELS[period]}
        </div>
      ))}
    </div>
  )
}

export function useClipboard() {
  const { showToast } = useToast()
  return useCallback(
    async (text: string, message = 'Copiado al portapapeles') => {
      try {
        await navigator.clipboard.writeText(text)
        showToast(message)
      } catch {
        showToast('No se ha podido copiar. Selecciona el texto manualmente.', 'error')
      }
    },
    [showToast],
  )
}

export function useNow() {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 60_000)
    return () => window.clearInterval(timer)
  }, [])
  return useMemo(() => now, [now])
}
