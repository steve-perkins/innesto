import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type Theme = 'system' | 'light' | 'dark' | 'sepia'
export type Flow = 'paginated' | 'scrolled'
export type FontFamily = 'book' | 'noto-serif' | 'noto-sans'

export const FONT_LABELS: Record<FontFamily, string> = {
  book: "Book default",
  'noto-serif': 'Noto Serif',
  'noto-sans': 'Noto Sans',
}

/** CSS font-family stack for a setting; null means leave the book's fonts alone. */
export function fontStack(f: FontFamily): string | null {
  switch (f) {
    case 'noto-serif': return "'Noto Serif', Georgia, 'Times New Roman', serif"
    case 'noto-sans': return "'Noto Sans', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
    default: return null
  }
}

export interface Settings {
  theme: Theme
  fontSize: number          // percent of the book's base size
  fontFamily: FontFamily
  lineHeight: number
  flow: Flow
  // Diglot-weave controls (used from phase 3 on).
  level: number             // 1..5: which candidates are eligible
  density: number           // swaps per 100 words
  swapColor: string
  targetLang: string
  voiceURI: string | null   // preferred TTS voice for the target language
}

interface SettingsStore extends Settings {
  set: (patch: Partial<Settings>) => void
}

export const defaultSettings: Settings = {
  theme: 'system',
  fontSize: 100,
  fontFamily: 'book',
  lineHeight: 1.5,
  flow: 'paginated',
  level: 1,
  density: 5,
  swapColor: '#2f7d4b',
  targetLang: 'it',
  voiceURI: null,
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
