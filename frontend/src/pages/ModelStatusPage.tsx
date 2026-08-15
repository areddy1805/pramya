import { useModelsStatus } from '../hooks/queries'
import { EmptyState, Pill, SectionHeading, Skeleton, StatusDot, Surface } from '../components/ui'

export function ModelStatusPage() {
  const status = useModelsStatus()

  if (status.isLoading) return <Skeleton className="h-64" />

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Runtime status</h1>
        <p className="mt-1 text-sm text-fg-2">Provider health, model registry, and the deterministic routing policy.</p>
      </header>

      {status.data ? (
        <>
          <div className="grid gap-4 sm:grid-cols-2">
            {status.data.providers.map((provider) => (
              <Surface key={provider.name} className="p-5">
                <div className="flex items-center justify-between">
                  <p className="font-medium text-fg">{provider.name}</p>
                  <span className="flex items-center gap-1.5">
                    <StatusDot tone={provider.healthy ? 'ok' : provider.configured ? 'danger' : 'neutral'} />
                    <Pill tone={provider.healthy ? 'ok' : provider.configured ? 'danger' : 'neutral'}>
                      {provider.healthy ? 'healthy' : provider.configured ? 'unreachable' : 'not configured'}
                    </Pill>
                  </span>
                </div>
                <p className="mt-1 text-xs text-fg-3">{provider.base_url ?? '—'}</p>
                {provider.models.length ? (
                  <ul className="mt-3 space-y-1">
                    {provider.models.map((m) => (
                      <li key={m} className="font-mono text-xs text-fg-2">· {m}</li>
                    ))}
                  </ul>
                ) : null}
              </Surface>
            ))}
          </div>

          <Surface className="p-6">
            <SectionHeading>Model registry</SectionHeading>
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-line text-[11px] uppercase tracking-wide text-fg-3">
                  <th className="py-2 pr-4">Model</th>
                  <th className="py-2 pr-4">Provider</th>
                  <th className="py-2 pr-4">Capability</th>
                  <th className="py-2">Thinking</th>
                </tr>
              </thead>
              <tbody>
                {status.data.models.map((m) => (
                  <tr key={m.id} className="border-b border-line">
                    <td className="py-2.5 pr-4 font-mono text-xs text-fg">{m.id}</td>
                    <td className="py-2.5 pr-4 text-fg-2">{m.provider}</td>
                    <td className="py-2.5 pr-4 text-fg-2">{m.capability}</td>
                    <td className="py-2.5 text-fg-2">{m.thinking ? 'on' : 'off'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Surface>

          <Surface className="p-6">
            <SectionHeading>Routing policy</SectionHeading>
            <p className="mb-3 text-xs text-fg-3">
              Deterministic task-class → model mapping. Local first; cloud escalation only where the policy names it.
            </p>
            {!status.data.policies.length ? (
              <EmptyState title="No policies registered" />
            ) : (
              <ul className="grid gap-2 text-sm sm:grid-cols-2">
                {status.data.policies.map((p) => (
                  <li key={p.task} className="flex items-center justify-between gap-2 rounded-lg border border-line px-3 py-2">
                    <span className="text-fg">{p.task}</span>
                    <span className="flex items-center gap-2">
                      <span className="font-mono text-xs text-accent">{p.model}</span>
                      {p.fallbacks.length ? (
                        <span className="text-[11px] text-fg-3">→ {p.fallbacks.join(', ')}</span>
                      ) : null}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Surface>
        </>
      ) : (
        <EmptyState title="Runtime status unavailable" body="The backend could not report provider health." />
      )}
    </div>
  )
}
