import { useModelsStatus } from '../hooks/queries'
import { Badge, Card, EmptyState, SectionTitle, Spinner } from '../components/ui'

export function ModelStatusPage() {
  const status = useModelsStatus()

  if (status.isLoading) return <Spinner label="Probing runtime…" />

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">Model / Runtime Status</h1>
        <p className="mt-1 text-sm text-slate-600">
          Provider health, canonical models, and the routing policy table.
        </p>
      </header>

      {status.data ? (
        <>
          <div className="grid gap-4 sm:grid-cols-2">
            {status.data.providers.map((provider) => (
              <Card key={provider.name}>
                <div className="flex items-center justify-between">
                  <p className="font-medium text-slate-800">{provider.name}</p>
                  <Badge tone={provider.healthy ? 'green' : provider.configured ? 'red' : 'slate'}>
                    {provider.healthy ? 'healthy' : provider.configured ? 'down' : 'not configured'}
                  </Badge>
                </div>
                <p className="mt-1 text-xs text-slate-500">{provider.base_url ?? '—'}</p>
                <ul className="mt-2 space-y-1 text-xs text-slate-600">
                  {provider.models.map((m) => (
                    <li key={m}>· {m}</li>
                  ))}
                </ul>
              </Card>
            ))}
          </div>

          <Card>
            <SectionTitle>Canonical models</SectionTitle>
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-xs uppercase text-slate-500">
                  <th className="py-2 pr-3">Model</th>
                  <th className="py-2 pr-3">Provider</th>
                  <th className="py-2 pr-3">Capability</th>
                  <th className="py-2">Thinking</th>
                </tr>
              </thead>
              <tbody>
                {status.data.models.map((m) => (
                  <tr key={m.id} className="border-b border-slate-100">
                    <td className="py-2 pr-3 font-mono text-xs text-slate-800">{m.id}</td>
                    <td className="py-2 pr-3 text-slate-600">{m.provider}</td>
                    <td className="py-2 pr-3 text-slate-600">{m.capability}</td>
                    <td className="py-2 text-slate-600">{m.thinking ? 'on' : 'off'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>

          <Card>
            <SectionTitle>Routing policy</SectionTitle>
            {!status.data.policies.length ? (
              <EmptyState title="No policies" />
            ) : (
              <ul className="grid gap-2 text-sm sm:grid-cols-2">
                {status.data.policies.map((p) => (
                  <li key={p.task} className="rounded-lg border border-slate-100 px-3 py-2">
                    <span className="font-medium text-slate-700">{p.task}</span>
                    <span className="ml-2 font-mono text-xs text-blue-700">{p.model}</span>
                    {p.fallbacks.length ? (
                      <span className="ml-2 text-xs text-slate-400">fallback: {p.fallbacks.join(', ')}</span>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </>
      ) : (
        <EmptyState title="Runtime status unavailable" />
      )}
    </div>
  )
}
