// Theme store: Dark (default) / Light / System, persisted, instant switch.

import { create } from 'zustand'
import { applyTheme, loadTheme, resolveTheme, watchSystemTheme } from '../lib/theme'

interface ThemeState {
  mode: 'dark' | 'light' | 'system'
  resolved: 'dark' | 'light'
  setMode: (mode: 'dark' | 'light' | 'system') => void
}

function initial(): { mode: 'dark' | 'light' | 'system'; resolved: 'dark' | 'light' } {
  const mode = loadTheme()
  return { mode, resolved: resolveTheme(mode) }
}

const initialValue = initial()

export const useTheme = create<ThemeState>((set) => ({
  ...initialValue,
  setMode: (mode) => {
    applyTheme(mode)
    set({ mode, resolved: resolveTheme(mode) })
  },
}))

// Keep System mode in sync with OS changes.
watchSystemTheme(() => {
  const state = useTheme.getState()
  if (state.mode === 'system') {
    useTheme.setState({ resolved: resolveTheme('system') })
  }
})
