// Pramya UI primitives — one system, no per-page reinvention.
// Editorial surfaces, restrained borders, 4px rhythm, deliberate accents.

import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from 'react'

// --- Surface ---------------------------------------------------------------

export function Surface({ children, className = '', tone = 'default' }: { children: ReactNode; className?: string; tone?: 'default' | 'inset' | 'accent' }) {
  const tones = {
    default: 'border border-ink-200 bg-white shadow-[0_1px_2px_rgba(15,23,42,0.04)]',
    inset: 'border border-ink-200 bg-ink-50',
    accent: 'border border-accent-200 bg-accent-50/40',
  }[tone]
  return <div className={`rounded-xl ${tones} ${className}`}>{children}</div>
}

export function SectionHeading({ children, aside }: { children: ReactNode; aside?: ReactNode }) {
  return (
    <div className="mb-3 flex items-center justify-between gap-3">
      <h2 className="text-xs font-semibold uppercase tracking-[0.08em] text-ink-500">{children}</h2>
      {aside}
    </div>
  )
}

// --- Buttons ---------------------------------------------------------------

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  size?: 'sm' | 'md' | 'lg'
}

export function Button({ children, variant = 'primary', size = 'md', className = '', ...rest }: ButtonProps) {
  const variants = {
    primary: 'bg-accent-700 text-white hover:bg-accent-800 active:bg-accent-900 disabled:bg-ink-200 disabled:text-ink-400',
    secondary: 'bg-white text-ink-700 border border-ink-200 hover:border-ink-300 hover:bg-ink-50 disabled:opacity-50',
    ghost: 'text-accent-700 hover:bg-accent-50 disabled:opacity-50',
    danger: 'bg-danger-700 text-white hover:bg-danger-800 disabled:bg-ink-200 disabled:text-ink-400',
  }[variant]
  const sizes = {
    sm: 'px-2.5 py-1.5 text-xs',
    md: 'px-3.5 py-2 text-sm',
    lg: 'px-5 py-2.5 text-sm',
  }[size]
  return (
    <button
      type="button"
      className={`inline-flex items-center justify-center gap-1.5 rounded-lg font-medium transition-colors disabled:cursor-not-allowed ${variants} ${sizes} ${className}`}
      {...rest}
    >
      {children}
    </button>
  )
}

// --- Form controls ----------------------------------------------------------

const fieldClass =
  'w-full rounded-lg border border-ink-200 bg-white px-3 py-2 text-sm text-ink-900 placeholder:text-ink-400 focus:border-accent-600 focus:outline-none focus:ring-2 focus:ring-accent-600/20 disabled:bg-ink-50'

export function TextInput(props: InputHTMLAttributes<HTMLInputElement>) {
  const { className = '', ...rest } = props
  return <input className={`${fieldClass} ${className}`} {...rest} />
}

export function TextArea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  const { className = '', ...rest } = props
  return <textarea className={`${fieldClass} ${className}`} {...rest} />
}

export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) {
  const { className = '', children, ...rest } = props
  return (
    <select className={`${fieldClass} ${className}`} {...rest}>
      {children}
    </select>
  )
}

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block text-[13px] font-medium text-ink-700">{label}</span>
      {children}
      {hint ? <span className="mt-1 block text-xs text-ink-400">{hint}</span> : null}
    </label>
  )
}

// --- Status -----------------------------------------------------------------

export function StatusDot({ tone }: { tone: 'ok' | 'warn' | 'danger' | 'neutral' | 'active' }) {
  const tones = {
    ok: 'bg-ok-700',
    warn: 'bg-warn-700',
    danger: 'bg-danger-700',
    neutral: 'bg-ink-300',
    active: 'bg-accent-600 animate-pulse',
  }[tone]
  return <span aria-hidden className={`inline-block h-2 w-2 rounded-full ${tones}`} />
}

export function Pill({ children, tone = 'neutral' }: { children: ReactNode; tone?: 'neutral' | 'ok' | 'warn' | 'danger' | 'accent' }) {
  const tones = {
    neutral: 'bg-ink-100 text-ink-600',
    ok: 'bg-ok-50 text-ok-700 border border-ok-100',
    warn: 'bg-warn-50 text-warn-700 border border-warn-100',
    danger: 'bg-danger-50 text-danger-700 border border-danger-100',
    accent: 'bg-accent-50 text-accent-700 border border-accent-100',
  }[tone]
  return <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${tones}`}>{children}</span>
}

// --- Progress ---------------------------------------------------------------

export function Meter({ value, max = 10, tone = 'accent' }: { value: number; max?: number; tone?: 'accent' | 'ok' | 'danger' }) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100))
  const tones = {
    accent: 'bg-accent-600',
    ok: 'bg-ok-700',
    danger: 'bg-danger-700',
  }[tone]
  return (
    <div role="progressbar" aria-valuenow={value} aria-valuemin={0} aria-valuemax={max} className="h-1.5 w-full overflow-hidden rounded-full bg-ink-100">
      <div className={`h-full rounded-full transition-all duration-500 ${tones}`} style={{ width: `${pct}%` }} />
    </div>
  )
}

// --- States -----------------------------------------------------------------

export function Spinner({ label = 'Working…', subtle = false }: { label?: string; subtle?: boolean }) {
  return (
    <div role="status" className={`flex items-center gap-2 text-sm ${subtle ? 'text-ink-400' : 'text-ink-500'}`}>
      <span aria-hidden className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-ink-200 border-t-accent-600" />
      {label}
    </div>
  )
}

export function Skeleton({ className = '' }: { className?: string }) {
  return <div aria-hidden className={`animate-pulse rounded-lg bg-ink-100 ${className}`} />
}

export function EmptyState({ icon, title, body, action }: { icon?: string; title: string; body?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-ink-300 bg-ink-50/60 px-6 py-12 text-center">
      {icon ? <span aria-hidden className="mb-3 text-2xl">{icon}</span> : null}
      <p className="text-sm font-semibold text-ink-800">{title}</p>
      {body ? <p className="mt-1.5 max-w-sm text-sm leading-relaxed text-ink-500">{body}</p> : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  )
}

export function ErrorState({ title = 'Something went wrong', body, onRetry }: { title?: string; body?: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="rounded-xl border border-danger-100 bg-danger-50 px-4 py-4">
      <p className="text-sm font-semibold text-danger-700">{title}</p>
      {body ? <p className="mt-1 text-sm text-danger-700/80">{body}</p> : null}
      {onRetry ? (
        <button className="mt-2 text-sm font-medium text-danger-700 underline hover:text-danger-800" onClick={onRetry}>
          Try again
        </button>
      ) : null}
    </div>
  )
}

// --- Data display -----------------------------------------------------------

export function KeyValue({ k, v }: { k: string; v: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-1.5 text-sm">
      <dt className="text-ink-500">{k}</dt>
      <dd className="text-right font-medium text-ink-800">{v}</dd>
    </div>
  )
}

export function Stat({ label, value, sub }: { label: string; value: ReactNode; sub?: string }) {
  return (
    <div className="min-w-0">
      <p className="text-xs font-medium uppercase tracking-wide text-ink-400">{label}</p>
      <p className="mt-1 text-2xl font-semibold tracking-tight text-ink-900">{value}</p>
      {sub ? <p className="mt-0.5 truncate text-xs text-ink-400">{sub}</p> : null}
    </div>
  )
}

export function Divider({ className = '' }: { className?: string }) {
  return <div role="separator" className={`h-px bg-ink-100 ${className}`} />
}
