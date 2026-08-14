// Header profile switcher: lists the user's career profiles, shows the
// active one, and switches the workspace context (server-persisted).

import { useState } from 'react'
import {
  DEFAULT_USER_ID,
  useResolvedProfile,
  useSetActiveProfile,
} from '../hooks/queries'
import { Spinner } from './ui'

export function ProfileSwitcher() {
  const userId = DEFAULT_USER_ID
  const { active, profiles, isLoading } = useResolvedProfile(userId)
  const setActive = useSetActiveProfile(userId)
  const [open, setOpen] = useState(false)

  if (isLoading) {
    return <Spinner label="Profiles" />
  }

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex max-w-44 items-center gap-1.5 rounded-lg border border-line bg-surface px-2.5 py-1.5 text-[13px] font-medium text-fg transition-colors hover:border-fg-3"
        aria-haspopup="listbox"
        aria-expanded={open}
        title={active ? `Active profile: ${active.name}` : 'No profile'}
      >
        <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-accent" />
        <span className="truncate">{active ? active.name : 'No profile'}</span>
        <span aria-hidden className="text-fg-3">▾</span>
      </button>
      {open ? (
        <>
          <button
            aria-label="Close profile menu"
            className="fixed inset-0 z-40 cursor-default"
            onClick={() => setOpen(false)}
          />
          <div
            role="listbox"
            aria-label="Switch career profile"
            className="absolute right-0 z-50 mt-1.5 w-60 overflow-hidden rounded-xl border border-line bg-surface shadow-[var(--shadow-2)]"
          >
            {profiles.length === 0 ? (
              <p className="px-3 py-2.5 text-xs text-fg-3">No profiles yet — create one on the Profiles page.</p>
            ) : (
              profiles.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  role="option"
                  aria-selected={p.id === active?.id}
                  onClick={() => {
                    setOpen(false)
                    if (p.id !== active?.id) void setActive.mutateAsync(p.id)
                  }}
                  className={`block w-full px-3 py-2.5 text-left text-[13px] transition-colors ${
                    p.id === active?.id
                      ? 'bg-accent-soft font-medium text-accent'
                      : 'text-fg hover:bg-track'
                  }`}
                >
                  <span className="block truncate">{p.name}</span>
                  {p.id === active?.id ? (
                    <span className="block text-[11px] text-accent">active workspace</span>
                  ) : null}
                </button>
              ))
            )}
          </div>
        </>
      ) : null}
    </div>
  )
}
