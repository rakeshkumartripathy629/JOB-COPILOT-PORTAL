import { create } from 'zustand'

type Theme = 'light' | 'dark'

interface ThemeState {
  theme: Theme
  toggle: () => void
}

function applyTheme(theme: Theme) {
  if (typeof document !== 'undefined') {
    document.documentElement.classList.toggle('dark', theme === 'dark')
  }
}

const initial: Theme =
  typeof window !== 'undefined' &&
  (window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false)
    ? 'dark'
    : 'light'

applyTheme(initial)

export const useThemeStore = create<ThemeState>((set) => ({
  theme: initial,
  toggle: () =>
    set((s) => {
      const next = s.theme === 'light' ? 'dark' : 'light'
      applyTheme(next)
      return { theme: next }
    }),
}))
