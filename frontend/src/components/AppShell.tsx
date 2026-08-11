import { NavLink, Navigate, Route, Routes } from 'react-router-dom'
import { DashboardPage } from '../pages/DashboardPage'
import { SetupPage } from '../pages/SetupPage'
import { PreparationPage } from '../pages/PreparationPage'
import { InterviewPage } from '../pages/InterviewPage'
import { ProgressPage } from '../pages/ProgressPage'
import { StoriesPage } from '../pages/StoriesPage'
import { SettingsPage } from '../pages/SettingsPage'
import { ModelStatusPage } from '../pages/ModelStatusPage'

const navItems = [
  { to: '/dashboard', label: 'Dashboard' },
  { to: '/setup', label: 'Setup' },
  { to: '/preparation', label: 'Preparation' },
  { to: '/interview', label: 'Interview' },
  { to: '/progress', label: 'Progress' },
  { to: '/stories', label: 'Stories' },
  { to: '/settings', label: 'Settings' },
  { to: '/models', label: 'Models' },
]

export function AppShell() {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
          <span className="text-lg font-semibold">Pramya</span>
          <nav aria-label="Main navigation" className="flex gap-4 text-sm">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  isActive
                    ? 'font-medium text-blue-700'
                    : 'text-slate-600 hover:text-slate-900'
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6">
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/setup" element={<SetupPage />} />
          <Route path="/preparation" element={<PreparationPage />} />
          <Route path="/interview" element={<InterviewPage />} />
          <Route path="/progress" element={<ProgressPage />} />
          <Route path="/stories" element={<StoriesPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/models" element={<ModelStatusPage />} />
        </Routes>
      </main>
    </div>
  )
}
