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
  { to: '/profile', label: 'Profiles' },
  { to: '/setup', label: 'Profile & Role' },
  { to: '/preparation', label: 'Preparation' },
  { to: '/interview', label: 'Practice' },
  { to: '/progress', label: 'Progress' },
  { to: '/evidence', label: 'Evidence' },
  { to: '/stories', label: 'Stories' },
  { to: '/history', label: 'History' },
]

const secondaryNav = [
  { to: '/debriefs', label: 'Debriefs' },
  { to: '/settings', label: 'Settings' },
  { to: '/models', label: 'Runtime' },
]

function NavLinkItem({ to, label }: { to: string; label: string }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `rounded-md px-2.5 py-1.5 text-[13px] font-medium transition-colors ${
          isActive ? 'bg-accent-soft text-accent' : 'text-fg-2 hover:bg-track hover:text-fg'
        }`
      }
    >
      {label}
    </NavLink>
  )
}

export function AppShell() {
  return (
    <div className="min-h-screen bg-canvas text-fg">
      <header className="sticky top-0 z-30 border-b border-line bg-surface/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-2.5 sm:px-6">
          <div className="flex items-baseline gap-2">
            <span className="text-[17px] font-semibold tracking-tight">Pramya</span>
            <span className="hidden text-[11px] font-medium text-fg-3 sm:block">evidence-driven interview prep</span>
          </div>
          <ProfileSwitcher />
          <nav aria-label="Primary" className="flex flex-wrap items-center gap-1">
            {primaryNav.map((item) => (
              <NavLinkItem key={item.to} {...item} />
            ))}
            <span aria-hidden className="mx-1 h-4 w-px bg-track" />
            {secondaryNav.map((item) => (
              <NavLinkItem key={item.to} {...item} />
            ))}
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
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
