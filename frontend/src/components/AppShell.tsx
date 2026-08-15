import { useEffect, useRef, useState } from 'react'
import { NavLink, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { DashboardPage } from '../pages/DashboardPage'
import { SetupPage } from '../pages/SetupPage'
import { PreparationPage } from '../pages/PreparationPage'
import { InterviewPage } from '../pages/InterviewPage'
import { ReportPage } from '../pages/ReportPage'
import { ProgressPage } from '../pages/ProgressPage'
import { StoriesPage } from '../pages/StoriesPage'
import { EvidencePage } from '../pages/EvidencePage'
import { SettingsPage } from '../pages/SettingsPage'
import { ModelStatusPage } from '../pages/ModelStatusPage'
import { HistoryPage } from '../pages/HistoryPage'
import { DebriefPage } from '../pages/DebriefPage'
import { TranscriptPage } from '../pages/TranscriptPage'
import { ProfilePage } from '../pages/ProfilePage'
import { ProfileSwitcher } from './ProfileSwitcher'
import { DEFAULT_USER_ID, useInterviews, useResolvedProfile } from '../hooks/queries'

const primaryNav = [
  { to: '/dashboard', label: 'Overview' },
  { to: '/preparation', label: 'Preparation' },
  { to: '/interview', label: 'Practice' },
  { to: '/evidence', label: 'Evidence' },
  { to: '/progress', label: 'Progress' },
]

const secondaryNav = [
  { to: '/profile', label: 'Profile' },
  { to: '/history', label: 'History' },
  { to: '/settings', label: 'Settings' },
  { to: '/models', label: 'Runtime' },
]

function NavLinkItem({ to, label }: { to: string; label: string }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `relative whitespace-nowrap px-1.5 py-1 text-[13px] font-medium transition-colors ${
          isActive ? 'text-fg' : 'text-fg-3 hover:text-fg-2'
        }`
      }
    >
      {({ isActive }) => (
        <>
          {label}
          {isActive ? <span aria-hidden className="absolute inset-x-1 -bottom-0.5 h-px bg-accent" /> : null}
        </>
      )}
    </NavLink>
  )
}

// Secondary records menu — the discoverability mechanism for the five
// routes that are not primary tabs (Setup, Report, Transcript, Debrief,
// Stories). One compact disclosure in the shell; same nav vocabulary as
// the primary items (text + 1px underline for the active state). Report
// and Transcript need a session id, so they resolve to the most recent
// session on record — or render disabled with an honest note when none
// exists. Direct URL navigation is untouched.
function MoreMenu() {
  const { activeId } = useResolvedProfile(DEFAULT_USER_ID)
  const latest = useInterviews(DEFAULT_USER_ID, activeId, { limit: 1 })
  const latestCompleted = useInterviews(DEFAULT_USER_ID, activeId, { limit: 1, statuses: ['completed'] })
  const { pathname } = useLocation()
  const [open, setOpen] = useState(false)
  const btnRef = useRef<HTMLButtonElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)
  const openedByKeyboard = useRef(false)

  const transcriptId = latest.data?.[0]?.id ?? null
  const reportId = latestCompleted.data?.[0]?.id ?? null

  const onSetup = pathname === '/setup'
  const onDebriefs = pathname === '/debriefs'
  const onStories = pathname === '/stories'
  const onReport = /^\/interview\/\d+\/report$/.test(pathname)
  const onTranscript = /^\/interview\/\d+\/transcript$/.test(pathname)
  const secondaryActive = onSetup || onDebriefs || onStories

  // Close on outside click and on Escape.
  useEffect(() => {
    if (!open) return
    function onDown(e: MouseEvent) {
      const t = e.target as Node
      if (btnRef.current?.contains(t) || menuRef.current?.contains(t)) return
      setOpen(false)
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        setOpen(false)
        btnRef.current?.focus()
      }
    }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  // When opened with the keyboard, move focus into the menu so arrow
  // navigation continues from the first item (standard menu-button).
  useEffect(() => {
    if (open && openedByKeyboard.current) {
      const first = menuRef.current?.querySelector<HTMLElement>('a[href]')
      first?.focus()
      openedByKeyboard.current = false
    }
  }, [open])

  function onBtnKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault()
      if (open) {
        const items = menuRef.current?.querySelectorAll<HTMLElement>('a[href]') ?? []
        const target = e.key === 'ArrowDown' ? items[0] : items[items.length - 1]
        target?.focus()
      } else {
        openedByKeyboard.current = true
        setOpen(true)
      }
    }
  }

  // Arrow-key navigation across the menu items (skips disabled rows).
  function onMenuKeyDown(e: React.KeyboardEvent) {
    if (!open) return
    const items = Array.from(menuRef.current?.querySelectorAll<HTMLElement>('a[href]') ?? [])
    if (items.length === 0) return
    const idx = items.indexOf(document.activeElement as HTMLElement)
    let next = -1
    if (e.key === 'ArrowDown') next = (idx + 1) % items.length
    else if (e.key === 'ArrowUp') next = (idx - 1 + items.length) % items.length
    else if (e.key === 'Home') next = 0
    else if (e.key === 'End') next = items.length - 1
    else return
    e.preventDefault()
    items[next]?.focus()
  }

  type Item = { label: string; to: string | null; route: string; active: boolean; note?: string }
  const items: Item[] = [
    { label: 'Setup', to: '/setup', route: '/setup', active: onSetup },
    { label: 'Transcript', to: transcriptId != null ? `/interview/${transcriptId}/transcript` : null, route: '/interview/:id/transcript', active: onTranscript, note: transcriptId == null ? 'no session yet' : undefined },
    { label: 'Debrief', to: '/debriefs', route: '/debriefs', active: onDebriefs },
    { label: 'Stories', to: '/stories', route: '/stories', active: onStories },
    { label: 'Report', to: reportId != null ? `/interview/${reportId}/report` : null, route: '/interview/:id/report', active: onReport, note: reportId == null ? 'no completed session' : undefined },
  ]

  return (
    <div className="relative">
      <button
        ref={btnRef}
        type="button"
        aria-expanded={open}
        aria-controls="more-menu"
        onClick={() => setOpen((o) => !o)}
        onKeyDown={onBtnKeyDown}
        className={`relative whitespace-nowrap px-1.5 py-1 text-[13px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent ${
          open || secondaryActive ? 'text-fg' : 'text-fg-3 hover:text-fg-2'
        }`}
      >
        <span className="flex items-center gap-1">
          More
          <span aria-hidden className={`text-[10px] transition-transform ${open ? 'rotate-180' : ''}`}>▾</span>
        </span>
        {open || secondaryActive ? <span aria-hidden className="absolute inset-x-1 -bottom-0.5 h-px bg-accent" /> : null}
      </button>
      {open ? (
        <div
          id="more-menu"
          ref={menuRef}
          aria-label="Secondary records"
          onKeyDown={onMenuKeyDown}
          className="fixed right-4 top-20 z-50 w-64 max-w-[calc(100vw-2rem)] border border-ink/30 bg-sheet text-ink shadow-[var(--shadow-1)] md:absolute md:right-0 md:top-full md:mt-1 md:w-60"
        >
          <p className="stencil px-3 pb-1.5 pt-2.5 text-[10px] uppercase tracking-[0.14em] text-ink-3">
            More · secondary records
          </p>
          <ul className="pb-1.5">
            {items.map((item) =>
              item.to ? (
                <li key={item.label}>
                  <NavLink
                    to={item.to}
                    onClick={() => setOpen(false)}
                    className={({ isActive }) =>
                      `flex items-baseline justify-between gap-3 px-3 py-2 text-[13px] transition-colors focus-visible:outline-none focus-visible:shadow-[var(--focus-ring)] ${
                        isActive ? 'bg-draft-soft/40 text-draft-2' : 'text-ink hover:bg-draft-soft/20'
                      }`
                    }
                  >
                    {({ isActive }) => (
                      <>
                        <span className="min-w-0 truncate">{item.label}</span>
                        <span className={`stencil shrink-0 text-[10px] uppercase tracking-[0.1em] ${isActive ? 'text-draft-2' : 'text-ink-3'}`}>
                          {item.route}
                        </span>
                      </>
                    )}
                  </NavLink>
                </li>
              ) : (
                <li key={item.label}>
                  <span
                    aria-disabled="true"
                    title={item.note ?? 'unavailable'}
                    className="flex cursor-not-allowed items-baseline justify-between gap-3 px-3 py-2 text-[13px] text-ink-3"
                  >
                    <span className="min-w-0 truncate">{item.label}</span>
                    <span className="stencil shrink-0 text-[10px] uppercase tracking-[0.1em] text-ink-3">
                      {item.note ?? item.route}
                    </span>
                  </span>
                </li>
              ),
            )}
          </ul>
        </div>
      ) : null}
    </div>
  )
}

export function AppShell() {
  return (
    <div className="min-h-screen bg-canvas text-fg">
      <header className="glass sticky top-0 z-30 border-b border-line">
        <div className="mx-auto flex h-11 max-w-6xl items-center justify-between gap-3 px-4 sm:px-6">
          <div className="flex min-w-0 items-center gap-4">
            <NavLink to="/dashboard" className="flex shrink-0 items-baseline gap-1.5">
              <span className="text-[15px] font-semibold tracking-tight text-fg">Pramya</span>
              <span aria-hidden className="hidden text-[10px] font-medium text-fg-3 sm:inline">prove you're ready</span>
            </NavLink>
            <span aria-hidden className="h-4 w-px bg-line" />
            <nav aria-label="Primary" className="hidden items-center gap-2 md:flex">
              {primaryNav.map((item) => (
                <NavLinkItem key={item.to} {...item} />
              ))}
            </nav>
          </div>

          <div className="flex min-w-0 items-center gap-3">
            <nav aria-label="Secondary" className="hidden items-center gap-2 lg:flex">
              {secondaryNav.map((item) => (
                <NavLinkItem key={item.to} {...item} />
              ))}
              <MoreMenu />
            </nav>
            <span aria-hidden className="hidden h-4 w-px bg-line lg:block" />
            <ProfileSwitcher />
          </div>
        </div>
        {/* Mobile primary nav — horizontal scroll row */}
        <nav aria-label="Primary (mobile)" className="flex items-center gap-1 overflow-x-auto border-t border-hairline px-3 py-1 md:hidden thin-scroll">
          {[...primaryNav, ...secondaryNav].map((item) => (
            <NavLinkItem key={item.to} {...item} />
          ))}
          <MoreMenu />
        </nav>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-6 sm:px-6">
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="/setup" element={<SetupPage />} />
          <Route path="/preparation" element={<PreparationPage />} />
          <Route path="/interview" element={<InterviewPage />} />
          <Route path="/interview/:id/report" element={<ReportPage />} />
          <Route path="/progress" element={<ProgressPage />} />
          <Route path="/evidence" element={<EvidencePage />} />
          <Route path="/stories" element={<StoriesPage />} />
          <Route path="/history" element={<HistoryPage />} />
          <Route path="/interview/:id/transcript" element={<TranscriptPage />} />
          <Route path="/debriefs" element={<DebriefPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/models" element={<ModelStatusPage />} />
        </Routes>
      </main>
    </div>
  )
}
