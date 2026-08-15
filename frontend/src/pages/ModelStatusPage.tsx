// Runtime — operational inspection record. Answers: is Pramya operational,
// which runtime services are available, which model capabilities exist, and
// where the failure is. Inspection only — configuration lives in Settings.
// Every value comes from the live health + model-status endpoints; nothing
// is fabricated (no latency/uptime/telemetry exists in the data).

import { useHealth, useModelsStatus } from '../hooks/queries'
import { Skeleton } from '../components/ui'
import { Sheet, SheetSection, StencilNum } from '../components/sheet'

function pad2(n: number): string {
  return String(n).padStart(2, '0')
}

// --- Runtime state cell -------------------------------------------------------

// State classification from what is actually known. Not a score: a
// deterministic reading of health + provider inspection.
type RuntimeState = 'OPERATIONAL' | 'DEGRADED' | 'UNAVAILABLE' | 'UNKNOWN'

function classify(healthOk: boolean | null, modelsOk: boolean | null, providersHealthy: boolean | null): RuntimeState {
  if (healthOk === true && modelsOk === true) return providersHealthy === true ? 'OPERATIONAL' : providersHealthy === false ? 'DEGRADED' : 'UNKNOWN'
  if (healthOk === false && modelsOk === false) return 'UNAVAILABLE'
  if (healthOk === true || modelsOk === true) return 'DEGRADED'
  return 'UNKNOWN'
}

function StateCell({
  state,
  env,
  backend,
  providers,
  models,
  localAi,
}: {
  state: RuntimeState
  env: string | null
  backend: string
  providers: number | null
  models: number | null
  localAi: string
}) {
  const tone = state === 'OPERATIONAL' ? 'text-draft' : state === 'UNKNOWN' ? 'text-ink-3' : 'text-redline'
  return (
    <div className="w-full border border-ink/30 bg-sheet-lit/45 px-4 py-3 sm:w-[17rem]">
      <div className="flex items-baseline justify-between gap-3">
        <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-2">Runtime state</p>
        <span className={`stencil text-[10px] uppercase tracking-[0.16em] ${tone}`}>{state}</span>
      </div>
      <dl className="mt-2">
        {[
          ['Environment', env ?? '—'],
          ['Backend', backend],
          ['Model providers', providers != null ? `${providers} registered` : '—'],
          ['Model registry', models != null ? `${models} models` : '—'],
          ['Local AI', localAi],
          ['Check cadence', 'auto · 30 s'],
        ].map(([label, value]) => (
          <div key={label} className="flex items-baseline justify-between gap-3 border-t border-ink/15 pt-1.5">
            <dt className="stencil text-[10px] uppercase tracking-[0.12em] text-ink-3">{label}</dt>
            <dd className={`stencil truncate text-[10px] uppercase tracking-[0.12em] ${value === '—' ? 'text-ink-3' : value === 'unreachable' || value.includes('failed') ? 'text-redline' : value === 'enabled' || value === 'available' ? 'text-draft' : 'text-ink-2'}`}>
              {value}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  )
}

// Service state stencil: AVAILABLE (draft) / UNREACHABLE (redline) /
// NOT CONFIGURED (ink-3) / UNKNOWN (ink-2).
function ServiceRow({
  index,
  name,
  state,
  stateTone,
  detail,
}: {
  index: string
  name: string
  state: string
  stateTone: string
  detail: string
}) {
  return (
    <li className="grid grid-cols-[2rem_minmax(0,1fr)_auto] items-center gap-x-3 border-b border-ink/10 py-2 last:border-b-0">
      <StencilNum className="text-[11px] leading-none text-ink-3">{index}</StencilNum>
      <div className="min-w-0">
        <p className="truncate text-[13px] text-ink">{name}</p>
        <p className="truncate text-[11px] text-ink-3">{detail}</p>
      </div>
      <span className={`stencil shrink-0 text-[10px] uppercase tracking-[0.12em] ${stateTone}`}>{state}</span>
    </li>
  )
}

function providerTone(p: { healthy: boolean | null; configured: boolean }): { state: string; tone: string } {
  if (p.healthy === true) return { state: 'Available', tone: 'text-draft' }
  if (p.configured && p.healthy === false) return { state: 'Unreachable', tone: 'text-redline' }
  if (!p.configured) return { state: 'Not configured', tone: 'text-ink-3' }
  return { state: 'Unknown', tone: 'text-ink-2' }
}

export function ModelStatusPage() {
  const health = useHealth()
  const status = useModelsStatus()

  const data = status.data ?? null
  const healthOk = health.isError ? false : health.data?.status === 'ok' ? true : health.data ? false : null
  const modelsOk = status.isError ? false : data ? true : null
  const providersHealthy = data ? data.providers.every((p) => p.healthy === true) : null
  const state = classify(healthOk, modelsOk, providersHealthy)
  const backendState = health.isError ? 'Unreachable' : health.data?.status === 'ok' ? 'Available' : health.data ? health.data.status : 'Unknown'
  const backendTone = backendState === 'Available' ? 'text-draft' : backendState === 'Unreachable' ? 'text-redline' : 'text-ink-2'

  return (
    <Sheet aria-label="Runtime operations record">
      {/* Title block */}
      <div className="flex flex-wrap items-start justify-between gap-x-8 gap-y-4 border-b border-ink/25 px-6 pb-4 pt-5">
        <div className="min-w-0">
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-2">Pramya · Runtime · Operations</p>
          <h1 className="mt-1.5 text-xl font-semibold tracking-tight text-ink">Runtime status</h1>
          <p className="mt-1 max-w-xl text-[13px] leading-relaxed text-ink-2">
            Provider health, model registry, and the deterministic routing policy.
          </p>
        </div>
        <StateCell
          state={state}
          env={health.data?.env ?? null}
          backend={backendState}
          providers={data ? data.providers.length : null}
          models={data ? data.models.length : null}
          localAi={data ? (data.local_ai_enabled ? 'enabled' : 'disabled') : '—'}
        />
      </div>

      {/* Polling indicator */}
      {status.isFetching && !status.isLoading ? (
        <div className="border-b border-ink/15 px-6 py-2">
          <p className="stencil text-[10px] uppercase tracking-[0.14em] text-ink-3">checking provider health…</p>
        </div>
      ) : null}

      {/* Service / capability register */}
      <SheetSection
        title="Service register"
        aside={<span className="stencil text-[10px] uppercase tracking-[0.14em] text-ink-2">live inspection</span>}
      >
        {status.isLoading ? (
          <div className="space-y-2 py-2">
            <Skeleton className="h-10" />
            <Skeleton className="h-10" />
            <Skeleton className="h-10" />
          </div>
        ) : (
          <ol className="py-1">
            <ServiceRow index="01" name="Backend" state={backendState} stateTone={backendTone} detail={health.data ? `${health.data.app} v${health.data.version} · ${health.data.env}` : 'no metadata'} />
            {(data?.providers ?? []).map((p, i) => {
              const t = providerTone(p)
              return (
                <ServiceRow
                  key={p.name}
                  index={pad2(i + 2)}
                  name={`Model provider · ${p.name}`}
                  state={t.state}
                  stateTone={t.tone}
                  detail={`${p.base_url ?? 'no base url'} · ${p.models.length} models`}
                />
              )
            })}
          </ol>
        )}
      </SheetSection>

      {/* Model registry */}
      <SheetSection
        title="Model registry"
        aside={<span className="stencil text-[10px] uppercase tracking-[0.14em] text-ink-2">{data?.models.length ?? 0} models</span>}
      >
        {status.isLoading ? (
          <div className="space-y-2 py-2">
            <Skeleton className="h-8" />
            <Skeleton className="h-8" />
            <Skeleton className="h-8" />
          </div>
        ) : data && data.models.length ? (
          <ol className="py-1">
            {data.models.map((m, i) => (
              <li key={m.id} className="grid grid-cols-[2rem_minmax(0,1fr)_auto] items-center gap-x-3 border-b border-ink/10 py-2 last:border-b-0 md:grid-cols-[2rem_minmax(0,1fr)_8rem_6rem_4.5rem]">
                <StencilNum className="text-[11px] leading-none text-ink-3">{pad2(i + 1)}</StencilNum>
                <div className="min-w-0">
                  <p className="truncate text-[12px] text-ink">{m.id}</p>
                  <p className="text-[10px] uppercase tracking-[0.08em] text-ink-3 md:hidden">
                    {m.provider} · {m.capability} · thinking {m.thinking ? 'on' : 'off'}
                  </p>
                </div>
                <span className="hidden text-[11px] text-ink-2 md:block">{m.provider}</span>
                <span className="hidden text-[11px] text-ink-2 md:block">{m.capability}</span>
                <span className="stencil hidden text-[10px] uppercase tracking-[0.1em] text-ink-2 md:block">{m.thinking ? 'on' : 'off'}</span>
              </li>
            ))}
          </ol>
        ) : (
          <div className="border border-dashed border-ink/25 px-4 py-6 text-center">
            <p className="stencil text-[10px] uppercase tracking-[0.16em] text-ink-3">No models registered</p>
            <p className="mx-auto mt-2 max-w-sm text-[12px] leading-relaxed text-ink-2">Provider inspection returned no registry entries.</p>
          </div>
        )}
      </SheetSection>

      {/* Routing policy */}
      <SheetSection
        title="Routing policy"
        aside={<span className="stencil text-[10px] uppercase tracking-[0.14em] text-ink-2">{data?.policies.length ?? 0} routes</span>}
      >
        <p className="py-1 text-[12px] leading-relaxed text-ink-2">
          Deterministic task-class → model mapping. Local first; cloud escalation only where the policy names it.
        </p>
        {status.isLoading ? (
          <div className="space-y-2 py-2">
            <Skeleton className="h-8" />
            <Skeleton className="h-8" />
          </div>
        ) : data && data.policies.length ? (
          <ol className="py-1">
            {data.policies.map((p, i) => (
              <li key={p.task} className="grid grid-cols-[2rem_minmax(0,1fr)] items-center gap-x-3 border-b border-ink/10 py-1.5 last:border-b-0 md:grid-cols-[2rem_minmax(0,1fr)_14rem_minmax(0,1fr)]">
                <StencilNum className="text-[11px] leading-none text-ink-3">{pad2(i + 1)}</StencilNum>
                <div className="min-w-0">
                  <p className="truncate text-[12px] text-ink-2">{p.task}</p>
                  <p className="mt-0.5 truncate text-[11px] text-ink-3 md:hidden">
                    <span className="stencil text-[10px] uppercase tracking-[0.1em] text-draft">{p.model}</span>
                    {p.fallbacks.length ? <span className="ml-2">fb · {p.fallbacks.join(', ')}</span> : <span className="ml-2">no fallback</span>}
                  </p>
                </div>
                <p className="hidden min-w-0 truncate text-[11px] text-ink-3 md:col-start-3 md:block">
                  <span className="stencil text-[10px] uppercase tracking-[0.1em] text-draft">{p.model}</span>
                  {p.fallbacks.length ? <span className="ml-2">fb · {p.fallbacks.join(', ')}</span> : <span className="ml-2">no fallback</span>}
                </p>
              </li>
            ))}
          </ol>
        ) : (
          <div className="border border-dashed border-ink/25 px-4 py-6 text-center">
            <p className="stencil text-[10px] uppercase tracking-[0.16em] text-ink-3">No policies registered</p>
          </div>
        )}
      </SheetSection>

      {/* Error — structure stays visible, affected subsystem redline */}
      {status.isError || health.isError ? (
        <div className="mx-6 mb-4 border border-redline/50 bg-redline-soft/30 px-4 py-3">
          <p className="stencil text-[10px] uppercase tracking-[0.14em] text-redline">
            {status.isError && health.isError ? 'Runtime inspection unavailable' : 'Partial inspection failure'}
          </p>
          <p className="mt-1 text-[12px] leading-relaxed text-ink-2">
            {status.isError
              ? status.error instanceof Error
                ? status.error.message
                : 'Model status could not be resolved.'
              : ''}
            {health.isError ? 'Backend health could not be resolved.' : ''}
          </p>
          <button
            type="button"
            onClick={() => {
              void status.refetch()
              void health.refetch()
            }}
            className="stencil mt-2.5 flex h-8 items-center justify-between gap-3 border border-draft bg-draft-soft/40 px-3 text-[10px] font-semibold uppercase tracking-[0.14em] text-draft-2 transition-colors hover:bg-draft-soft/70 focus-visible:outline-none focus-visible:shadow-[var(--focus-ring)]"
          >
            <span>Re-check</span>
            <span aria-hidden>↻</span>
          </button>
        </div>
      ) : null}

      {/* Revision strip */}
      <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 border-t border-ink/25 px-6 pb-4 pt-3">
        <p className="stencil text-[10px] uppercase leading-relaxed tracking-[0.1em] text-ink-2">
          workspace 1 · env {health.data?.env ?? '—'} · runtime {state.toLowerCase().replace(/_/g, ' ')}
          <br />
          drawn {new Date().toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
        </p>
        <p className="stencil text-[10px] uppercase leading-relaxed tracking-[0.1em] text-ink-3">
          inspection only — configuration lives in Settings. auto-check every 30 s.
        </p>
      </div>
    </Sheet>
  )
}
