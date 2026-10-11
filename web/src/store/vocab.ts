// The reader's vocabulary state for the current target language, shared by
// the selection algorithm (what to swap) and the popover (marking words).
import { create } from 'zustand'
import { api } from '../api/client'

interface VocabStore {
  lang: string | null
  known: Set<string>
  learning: Set<string>
  load: (lang: string) => Promise<void>
  mark: (lang: string, lemmas: string[], status: 'known' | 'learning') => Promise<void>
  unmark: (lang: string, lemma: string) => Promise<void>
  lookup: (lang: string, lemmas: string[]) => void
}

export const useVocab = create<VocabStore>()((set, get) => ({
  lang: null,
  known: new Set(),
  learning: new Set(),

  async load(lang) {
    try {
      const s = await api.vocabSummary(lang)
      set({ lang, known: new Set(s.known), learning: new Set(s.learning) })
    } catch {
      if (get().lang !== lang) set({ lang, known: new Set(), learning: new Set() })
    }
  },

  async mark(lang, lemmas, status) {
    const known = new Set(get().known), learning = new Set(get().learning)
    for (const l of lemmas) {
      if (status === 'known') { known.add(l); learning.delete(l) }
      else { learning.add(l); known.delete(l) }
    }
    set({ known, learning })
    await Promise.all(lemmas.map((l) => api.upsertVocab(lang, l, status).catch(() => undefined)))
  },

  async unmark(lang, lemma) {
    const known = new Set(get().known), learning = new Set(get().learning)
    known.delete(lemma); learning.delete(lemma)
    set({ known, learning })
    await api.deleteVocab(lang, lemma).catch(() => undefined)
  },

  lookup(lang, lemmas) {
    // Fire-and-forget: a tapped word is implicitly one you are learning,
    // unless you already marked it known.
    const { known } = get()
    for (const l of lemmas) {
      if (!known.has(l)) void api.upsertVocab(lang, l, undefined, true).catch(() => undefined)
    }
  },
}))
