// Pramya UI primitives — one material system, both themes.
//
// Material rules (see index.css):
//  - Flat surfaces with hairline borders; no default shadow.
//  - Shadows only where something floats (menus, popovers).
//  - Status communicated by color + text together, never color alone.
//  - One accent; pills are status-only, tags are content-only.
//
// Components consume semantic tokens only; no raw colors.

import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from 'react'

// --- Micro label (section / metadata heading) --------------------------------

export function Micro({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <p className={`text-[11px] font-semibold uppercase tracking-[0.09em] text-fg-3 ${className}`}>
      {children}
    </p>
  )
}

// --- Surface -----------------------------------------------------------------

export function Surface({
  children,
  className = '',
  tone = 'default',
}: {
  children: ReactNode
  className?: string
  tone?: 'default' | 'inset' | 'accent' | 'raised'
}) {
  const tones = {
    default: 'border border-line bg-surface',
    inset: 'border border-line bg-surface-2',
    accent: 'border border-accent-line bg-accent-soft',
    raised: 'border border-line bg-surface shadow-[var(--shadow-1)]',
  }[tone]
  return <div className={`rounded-[var(--r-lg)] ${tones} ${className}`}>{children}</div>
}

export function SectionHeading({ children, aside }: { children: ReactNode; aside?: ReactNode }) {
  return (
    <div className="mb-3 flex items-baseline justify-between gap-3">
      <Micro>{children}</Micro>
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
    primary:
      'bg-accent text-white hover:bg-accent-hover active:brightness-95 disabled:bg-track disabled:text-fg-disabled',
    secondary:
      'border border-line bg-surface text-fg hover:border-fg-3 hover:bg-surface-2 active:bg-surface-3 disabled:opacity-50',
    ghost: 'text-accent hover:bg-accent-soft active:bg-accent-soft disabled:opacity-40',
    danger: 'bg-danger text-white hover:brightness-110 active:brightness-95 disabled:bg-track disabled:text-fg-disabled',
  }[variant]
  const sizes = {
    sm: 'px-2.5 py-1.5 text-xs',
    md: 'px-3.5 py-2 text-sm',
    lg: 'px-5 py-2.5 text-[15px]',
  }[size]
  return (
    <button
      type="button"
      className={`inline-flex items-center justify-center gap-1.5 rounded-[var(--r-md)] font-medium transition-all duration-[var(--dur-fast)] active:scale-[0.98] disabled:cursor-not-allowed disabled:active:scale-100 ${variants} ${sizes} ${className}`}
      {...rest}
    >
      {children}
    </button>
  )
}

// --- Segmented control -------------------------------------------------------

export function Seg({
  value,
  options,
  onChange,
  ariaLabel,
  className = '',
}: {
  value: string
  options: Array<{ value: string; label: string }>
  onChange: (value: string) => void
  ariaLabel: string
  className?: string
}) {
  return (
    <div role="group" aria-label={ariaLabel} className={`inline-flex rounded-[var(--r-md)] border border-line bg-surface-2 p-0.5 ${className}`}>
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          aria-pressed={value === o.value}
          onClick={() => onChange(o.value)}
          className={`rounded-[var(--r-sm)] px-2.5 py-1 text-xs font-medium transition-all duration-[var(--dur-fast)] ${
            value === o.value ? 'bg-surface text-fg shadow-[var(--shadow-1)]' : 'text-fg-2 hover:text-fg'
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

// --- Form controls -----------------------------------------------------------

const fieldClass =
  'w-full rounded-[var(--r-md)] border border-line bg-surface px-3 py-2 text-sm text-fg placeholder:text-fg-disabled focus:border-accent focus:outline-none focus:shadow-[var(--focus-ring)] disabled:bg-surface-2 disabled:text-fg-disabled'

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

export type StatusTone = 'ok' | 'warn' | 'danger' | 'neutral' | 'active'

export function StatusDot({ tone }: { tone: StatusTone }) {
  const tones: Record<StatusTone, string> = {
    ok: 'bg-ok',
    warn: 'bg-warn',
    danger: 'bg-danger',
    neutral: 'bg-fg-disabled',
    active: 'bg-accent',
  }
  const halos: Record<StatusTone, string> = {
    ok: 'rgba(62, 207, 142, 0.16)',
    warn: 'rgba(240, 180, 75, 0.16)',
    danger: 'rgba(240, 113, 113, 0.16)',
    neutral: 'transparent',
    active: 'rgba(110, 168, 255, 0.18)',
  }
  return (
    <span
      aria-hidden
      className={`state-dot inline-block h-2 w-2 ${tones[tone]}`}
      style={{ ['--dot-halo' as string]: halos[tone] }}
    />
  )
}

export function Pill({
  children,
  tone = 'neutral',
}: {
  children: ReactNode
  tone?: 'neutral' | 'ok' | 'warn' | 'danger' | 'accent'
}) {
  const tones = {
    neutral: 'bg-track text-fg-2',
    ok: 'bg-ok-soft text-ok',
    warn: 'bg-warn-soft text-warn',
    danger: 'bg-danger-soft text-danger',
    accent: 'bg-accent-soft text-accent',
  }[tone]
  return <span className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ${tones}`}>{children}</span>
}

// Tag: content chip (topics, provenance, gaps) — bordered, not colored.
export function Tag({ children }: { children: ReactNode }) {
  return <span className="inline-flex items-center rounded-[var(--r-sm)] border border-line bg-surface-2 px-2 py-0.5 text-xs text-fg-2">{children}</span>
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
    <div role="progressbar" aria-valuenow={value} aria-valuemin={0} aria-valuemax={max} className="h-1 w-full overflow-hidden rounded-full bg-track">
      <div className={`h-full rounded-full transition-all duration-500 ${tones}`} style={{ width: `${pct}%` }} />
    </div>
  )
}

// --- States ------------------------------------------------------------------

export function Spinner({ label = 'Working…', subtle = false }: { label?: string; subtle?: boolean }) {
  return (
    <div role="status" className={`flex items-center gap-2 text-sm ${subtle ? 'text-fg-3' : 'text-fg-2'}`}>
      <span aria-hidden className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-track border-t-accent" />
      {label}
    </div>
  )
}

export function Skeleton({ className = '' }: { className?: string }) {
  return <div aria-hidden className={`animate-pulse rounded-[var(--r-md)] bg-track ${className}`} />
}

export function EmptyState({
  title,
  body,
  action,
  className = '',
}: {
  title: string
  body?: string
  action?: ReactNode
  className?: string
}) {
  return (
    <div className={`flex flex-col gap-2 rounded-[var(--r-lg)] border border-line bg-surface-2 px-5 py-6 ${className}`}>
      <p className="text-sm font-semibold text-fg">{title}</p>
      {body ? <p className="max-w-md text-sm leading-relaxed text-fg-2">{body}</p> : null}
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  )
}

export function ErrorState({
  title = 'Something went wrong',
  body,
  onRetry,
  className = '',
}: {
  title?: string
  body?: string
  onRetry?: () => void
  className?: string
}) {
  return (
    <div role="alert" className={`flex items-start justify-between gap-4 rounded-[var(--r-lg)] border border-danger/25 bg-danger-soft px-4 py-3 ${className}`}>
      <div>
        <p className="text-sm font-semibold text-danger">{title}</p>
        {body ? <p className="mt-0.5 text-sm text-fg-2">{body}</p> : null}
      </div>
      {onRetry ? (
        <button className="shrink-0 text-sm font-medium text-danger underline underline-offset-2 hover:brightness-125" onClick={onRetry}>
          Try again
        </button>
      ) : null}
    </div>
  )
}

// --- Data display ------------------------------------------------------------

export function KeyValue({ k, v }: { k: string; v: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-1 text-sm">
      <dt className="text-fg-2">{k}</dt>
      <dd className="text-right font-medium text-fg">{v}</dd>
    </div>
  )
}

export function Stat({ label, value, sub }: { label: string; value: ReactNode; sub?: string }) {
  return (
    <div className="min-w-0">
      <Micro>{label}</Micro>
      <p className="tabular mt-0.5 text-xl font-semibold tracking-tight text-fg">{value}</p>
      {sub ? <p className="mt-0.5 truncate text-xs text-fg-3">{sub}</p> : null}
    </div>
  )
}

export function Divider({ className = '' }: { className?: string }) {
  return <div role="separator" className={`h-px bg-line ${className}`} />
}

// --- Document row ------------------------------------------------------------

export function DocumentRow({
  filename,
  statusTone = 'neutral',
  meta,
  selected = false,
  selectedLabel = 'current',
  actions,
  onClick,
}: {
  filename: string
  statusTone?: StatusTone
  meta?: string
  selected?: boolean
  selectedLabel?: string
  actions?: ReactNode
  onClick?: () => void
}) {
  return (
    <div
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onClick={onClick}
      onKeyDown={(e) => {
        if (onClick && (e.key === 'Enter' || e.key === ' ')) {
          e.preventDefault()
          onClick()
        }
      }}
      className={`group flex items-center justify-between gap-3 rounded-[var(--r-md)] border px-3 py-2 transition-colors ${
        selected ? 'border-accent-line bg-accent-soft' : 'border-transparent hover:border-line hover:bg-surface-2'
      }`}
    >
      <div className="flex min-w-0 items-center gap-2.5">
        <StatusDot tone={statusTone} />
        <div className="min-w-0">
          <p className={`truncate text-sm ${selected ? 'font-semibold text-fg' : 'font-medium text-fg'}`}>
            {filename}
            {selected ? <span className="ml-1.5 text-xs font-medium text-accent">{selectedLabel}</span> : null}
          </p>
          {meta ? <p className="truncate text-xs text-fg-3">{meta}</p> : null}
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-1.5 opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100">
        {actions}
      </div>
    </div>
  )
}
