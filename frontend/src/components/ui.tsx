// Pramya UI primitives — one material system, both themes.
// Components consume semantic tokens (--surface, --fg, --accent…); no raw
// colors. Dark is the flagship theme; light shares the same architecture.

import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from 'react'

// --- Surface -----------------------------------------------------------------

export function Surface({ children, className = '', tone = 'default' }: { children: ReactNode; className?: string; tone?: 'default' | 'inset' | 'accent' }) {
  const tones = {
    default: 'border border-line bg-surface shadow-[var(--shadow-1)]',
    inset: 'border border-line bg-surface-2',
    accent: 'border border-accent-line bg-accent-soft',
  }[tone]
  return <div className={`rounded-xl ${tones} ${className}`}>{children}</div>
}

export function GlassSurface({ children, className = '', elevated = false }: { children: ReactNode; className?: string; elevated?: boolean }) {
  return <div className={`rounded-xl ${elevated ? 'glass-2' : 'glass-1'} ${className}`}>{children}</div>
}

export function SectionHeading({ children, aside }: { children: ReactNode; aside?: ReactNode }) {
  return (
    <div className="mb-3 flex items-center justify-between gap-3">
      <h2 className="text-xs font-semibold uppercase tracking-[0.08em] text-fg-3">{children}</h2>
      {aside}
    </div>
  )
}

// --- Buttons -----------------------------------------------------------------

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  size?: 'sm' | 'md' | 'lg'
}

export function Button({ children, variant = 'primary', size = 'md', className = '', ...rest }: ButtonProps) {
  const variants = {
    primary: 'bg-accent text-white hover:bg-accent-hover active:brightness-95 disabled:bg-track disabled:text-fg-disabled',
    secondary: 'bg-surface text-fg border border-line hover:border-fg-3 hover:bg-surface-2 disabled:opacity-50',
    ghost: 'text-accent hover:bg-accent-soft disabled:opacity-50',
    danger: 'bg-danger text-white hover:brightness-110 disabled:bg-track disabled:text-fg-disabled',
  }[variant]
  const sizes = {
    sm: 'px-2.5 py-1.5 text-xs',
    md: 'px-3.5 py-2 text-sm',
    lg: 'px-5 py-2.5 text-sm',
  }[size]
  return (
    <button
      type="button"
      className={`inline-flex items-center justify-center gap-1.5 rounded-lg font-medium transition-all duration-[var(--dur-fast)] disabled:cursor-not-allowed ${variants} ${sizes} ${className}`}
      {...rest}
    >
      {children}
    </button>
  )
}

// --- Form controls -----------------------------------------------------------

const fieldClass =
  'w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm text-fg placeholder:text-fg-disabled focus:border-accent focus:outline-none focus:shadow-[var(--focus-ring)] disabled:bg-surface-2 disabled:text-fg-disabled'

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
      <span className="mb-1 block text-[13px] font-medium text-fg-2">{label}</span>
      {children}
      {hint ? <span className="mt-1 block text-xs text-fg-3">{hint}</span> : null}
    </label>
  )
}

// --- Status ------------------------------------------------------------------

export function StatusDot({ tone }: { tone: 'ok' | 'warn' | 'danger' | 'neutral' | 'active' }) {
  const tones = {
    ok: 'bg-ok',
    warn: 'bg-warn',
    danger: 'bg-danger',
    neutral: 'bg-fg-disabled',
    active: 'bg-accent animate-pulse',
  }[tone]
  return <span aria-hidden className={`inline-block h-2 w-2 rounded-full ${tones}`} />
}

export function Pill({ children, tone = 'neutral' }: { children: ReactNode; tone?: 'neutral' | 'ok' | 'warn' | 'danger' | 'accent' }) {
  const tones = {
    neutral: 'bg-track text-fg-2',
    ok: 'bg-ok-soft text-ok',
    warn: 'bg-warn-soft text-warn',
    danger: 'bg-danger-soft text-danger',
    accent: 'bg-accent-soft text-accent',
  }[tone]
  return <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${tones}`}>{children}</span>
}

// --- Progress ----------------------------------------------------------------

export function Meter({ value, max = 10, tone = 'accent' }: { value: number; max?: number; tone?: 'accent' | 'ok' | 'danger' }) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100))
  const tones = {
    accent: 'bg-accent',
    ok: 'bg-ok',
    danger: 'bg-danger',
  }[tone]
  return (
    <div role="progressbar" aria-valuenow={value} aria-valuemin={0} aria-valuemax={max} className="h-1.5 w-full overflow-hidden rounded-full bg-track">
      <div className={`h-full rounded-full transition-all duration-500 ${tones}`} style={{ width: `${pct}%` }} />
    </div>
  )
}

// --- States ------------------------------------------------------------------

export function Spinner({ label = 'Working…', subtle = false }: { label?: string; subtle?: boolean }) {
  return (
    <div role="status" className={`flex items-center gap-2 text-sm ${subtle ? 'text-fg-3' : 'text-fg-2'}`}>
      <span aria-hidden className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-track border-t-accent" />
      {label}
    </div>
  )
}

export function Skeleton({ className = '' }: { className?: string }) {
  return <div aria-hidden className={`animate-pulse rounded-lg bg-track ${className}`} />
}

export function EmptyState({ icon, title, body, action }: { icon?: string; title: string; body?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-line bg-surface-2 px-6 py-12 text-center">
      {icon ? <span aria-hidden className="mb-3 text-2xl opacity-70">{icon}</span> : null}
      <p className="text-sm font-semibold text-fg">{title}</p>
      {body ? <p className="mt-1.5 max-w-sm text-sm leading-relaxed text-fg-2">{body}</p> : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  )
}

export function ErrorState({ title = 'Something went wrong', body, onRetry }: { title?: string; body?: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="rounded-xl border border-danger-line bg-danger-soft px-4 py-4">
      <p className="text-sm font-semibold text-danger">{title}</p>
      {body ? <p className="mt-1 text-sm text-fg-2">{body}</p> : null}
      {onRetry ? (
        <button className="mt-2 text-sm font-medium text-danger underline hover:brightness-125" onClick={onRetry}>
          Try again
        </button>
      ) : null}
    </div>
  )
}

// --- Data display ------------------------------------------------------------

export function KeyValue({ k, v }: { k: string; v: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-1.5 text-sm">
      <dt className="text-fg-2">{k}</dt>
      <dd className="text-right font-medium text-fg">{v}</dd>
    </div>
  )
}

export function Stat({ label, value, sub }: { label: string; value: ReactNode; sub?: string }) {
  return (
    <div className="min-w-0">
      <p className="text-xs font-medium uppercase tracking-wide text-fg-3">{label}</p>
      <p className="tabular mt-1 text-2xl font-semibold tracking-tight text-fg">{value}</p>
      {sub ? <p className="mt-0.5 truncate text-xs text-fg-3">{sub}</p> : null}
    </div>
  )
}

export function Divider({ className = '' }: { className?: string }) {
  return <div role="separator" className={`h-px bg-line ${className}`} />
}
