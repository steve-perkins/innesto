import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type Theme = 'system' | 'light' | 'dark' | 'sepia'
export type Flow = 'paginated' | 'scrolled'

export interface Settings {
  theme: Theme
  fontSize: number          // percent of the book's base size
  lineHeight: number
  flow: Flow
  // Diglot-weave controls (used from phase 3 on).
  level: number             // 1..5: which candidates are eligible
  density: number           // swaps per 100 words
  swapColor: string
  targetLang: string
}

interface SettingsStore extends Settings {
  set: (patch: Partial<Settings>) => void
}

export const defaultSettings: Settings = {
  theme: 'system',
  fontSize: 100,
  lineHeight: 1.5,
  flow: 'paginated',
  level: 1,
  density: 5,
  swapColor: '#2f7d4b',
  targetLang: 'it',
}

export const useSettings = create<SettingsStore>()(
  persist(
    (set) => ({ ...defaultSettings, set: (patch) => set(patch) }),
    { name: 'innesto.settings' },
  ),
)

/** Resolve 'system' to a concrete theme. */
export function effectiveTheme(theme: Theme): Exclude<Theme, 'system'> {
  if (theme !== 'system') return theme
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}
