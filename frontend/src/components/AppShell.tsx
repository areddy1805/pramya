import { NavLink, Navigate, Route, Routes } from 'react-router-dom'
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
