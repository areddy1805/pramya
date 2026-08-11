// Theme system: Dark (default) / Light / System.
// Persisted in localStorage; applied before first paint via inline script
// in index.html (no flash-of-incorrect-theme); toggled instantly here.

export type ThemeMode = 'dark' | 'light' | 'system'

const STORAGE_KEY = 'pramya-theme'

export function resolveTheme(mode: ThemeMode): 'dark' | 'light' {
  if (mode === 'system') {
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  }
  return mode
}

export function applyTheme(mode: ThemeMode): void {
  const resolved = resolveTheme(mode)
  const root = document.documentElement
  root.classList.toggle('dark', resolved === 'dark')
  root.style.colorScheme = resolved
  // Keep the init script and this store in sync across tabs.
  localStorage.setItem(STORAGE_KEY, mode)
}

export function loadTheme(): ThemeMode {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored === 'dark' || stored === 'light' || stored === 'system') return stored
  } catch {
    /* storage unavailable — default */
  }
  return 'dark' // Pramya opens in Dark by default.
}

export function watchSystemTheme(onChange: () => void): () => void {
  const mq = window.matchMedia('(prefers-color-scheme: dark)')
  const listener = () => onChange()
  mq.addEventListener('change', listener)
  return () => mq.removeEventListener('change', listener)
}
