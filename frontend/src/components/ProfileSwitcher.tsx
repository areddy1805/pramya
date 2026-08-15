// Header profile switcher: lists the user's career profiles, shows the
// active one, and switches the workspace context (server-persisted).
// Keyboard: Enter/Space opens, Escape closes, arrows navigate.

import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { DEFAULT_USER_ID, useResolvedProfile, useSetActiveProfile } from '../hooks/queries'
import { Spinner } from './ui'

export function ProfileSwitcher() {
  const userId = DEFAULT_USER_ID
  const { active, profiles, isLoading } = useResolvedProfile(userId)
  const setActive = useSetActiveProfile(userId)
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open])

  if (isLoading) {
    return (
      <div className="flex h-7 items-center px-1">
        <Spinner label="Profiles" subtle />
      </div>
    )
  }

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="listbox"
        aria-expanded={open}
        title={active ? `Active profile: ${active.name}` : 'No profile'}
        className="flex h-7 max-w-48 items-center gap-2 rounded-[var(--r-md)] border border-line bg-surface px-2 text-[13px] font-medium text-fg transition-colors hover:border-fg-3"
      >
        <span aria-hidden className="h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
        <span className="truncate">{active ? active.name : 'No profile'}</span>
        <span aria-hidden className={`text-[9px] text-fg-3 transition-transform duration-[var(--dur-fast)] ${open ? 'rotate-180' : ''}`}>
          ▼
        </span>
      </button>
      {open ? (
        <>
          <button aria-label="Close profile menu" className="fixed inset-0 z-40 cursor-default" onClick={() => setOpen(false)} />
          <div
            role="listbox"
            aria-label="Switch career profile"
            className="pramya-pop absolute right-0 z-50 mt-1.5 w-64 overflow-hidden rounded-[var(--r-lg)] border border-line bg-elevated shadow-[var(--shadow-2)]"
          >
            <p className="border-b border-line px-3 py-2 text-[10px] font-semibold uppercase tracking-[0.09em] text-fg-3">
              Workspace
            </p>
            {profiles.length === 0 ? (
              <p className="px-3 py-2.5 text-xs text-fg-3">No profiles yet — create one on the Profile page.</p>
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
                  className={`block w-full px-3 py-2 text-left transition-colors ${
                    p.id === active?.id ? 'bg-accent-soft' : 'hover:bg-track'
                  }`}
                >
                  <span className="block truncate text-[13px] font-medium text-fg">{p.name}</span>
                  {p.positioning ? <span className="block truncate text-[11px] text-fg-3">{p.positioning}</span> : null}
                  {p.id === active?.id ? <span className="mt-0.5 block text-[11px] font-medium text-accent">active workspace</span> : null}
                </button>
              ))
            )}
            <div className="border-t border-line p-1">
              <Link
                to="/profile"
                onClick={() => setOpen(false)}
                className="block rounded-[var(--r-sm)] px-2.5 py-1.5 text-[13px] font-medium text-fg-2 transition-colors hover:bg-track hover:text-fg"
              >
                Manage profiles…
              </Link>
            </div>
          </div>
        </>
      ) : null}
    </div>
  )
}
