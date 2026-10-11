// Sidecar loading: small metadata up front, candidates per section on demand.
// Sections are immutable per sidecar id, so they are cached in IndexedDB for
// offline reading and never re-downloaded; metadata is re-checked when online
// (a re-processed or imported sidecar has a new id).
import Dexie, { type EntityTable } from 'dexie'
import type { Candidate } from '../reader/selection'
import { authFetch } from './auth'

export interface SectionMeta {
  index: number
  href: string
  textHash: string
  wordCount: number
  candidateCount: number
}

export interface SidecarMeta {
  id: number
  bookId: string
  sourceLang: string
  targetLang: string
  generator: { name: string; version: string; engine?: string; createdAt: string }
  sections: SectionMeta[]
}

export interface SidecarSection extends SectionMeta { candidates: Candidate[] }

interface CachedMeta { key: string; meta: SidecarMeta; savedAt: number }
interface CachedSection { key: string; sidecarId: number; index: number; candidates: Candidate[]; savedAt: number }

const db = new Dexie('innesto-sidecars') as Dexie & {
  metas: EntityTable<CachedMeta, 'key'>
  sections: EntityTable<CachedSection, 'key'>
}
db.version(1).stores({ sidecars: 'key' })
db.version(2).stores({ sidecars: null, metas: 'key', sections: 'key, sidecarId' })

export type SidecarStatus =
  | { kind: 'ready'; meta: SidecarMeta; sections: Map<number, SectionMeta> }
  | { kind: 'missing' }
  | { kind: 'error'; message: string }

export async function loadSidecar(bookId: string, lang: string): Promise<SidecarStatus> {
  const key = `${bookId}:${lang}`
  try {
    const res = await authFetch(`/api/books/${bookId}/sidecars/active/meta?lang=${encodeURIComponent(lang)}`)
    if (res.status === 404) {
      await db.metas.delete(key).catch(() => undefined)
      return { kind: 'missing' }
    }
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const meta = (await res.json()) as SidecarMeta
    const previous = await db.metas.get(key).catch(() => undefined)
    if (previous && previous.meta.id !== meta.id) {
      await db.sections.where('sidecarId').equals(previous.meta.id).delete().catch(() => undefined)
    }
    await db.metas.put({ key, meta, savedAt: Date.now() }).catch(() => undefined)
    return ready(meta)
  } catch (err) {
    const cached = await db.metas.get(key).catch(() => undefined)
    if (cached) return ready(cached.meta)
    return { kind: 'error', message: (err as Error).message }
  }
}

function ready(meta: SidecarMeta): SidecarStatus {
  return { kind: 'ready', meta, sections: new Map(meta.sections.map((s) => [s.index, s])) }
}

const inflight = new Map<string, Promise<Candidate[]>>()

/** Candidates for one section, from IndexedDB when present, else the server. */
export function loadSectionCandidates(sidecarId: number, index: number): Promise<Candidate[]> {
  const key = `${sidecarId}:${index}`
  let p = inflight.get(key)
  if (!p) {
    p = (async () => {
      const cached = await db.sections.get(key).catch(() => undefined)
      if (cached) return cached.candidates
      const res = await authFetch(`/api/sidecars/${sidecarId}/sections/${index}`)
      if (!res.ok) throw new Error(`Could not load translations for this chapter (HTTP ${res.status})`)
      const section = (await res.json()) as SidecarSection
      await db.sections.put({ key, sidecarId, index, candidates: section.candidates, savedAt: Date.now() })
        .catch(() => undefined)
      return section.candidates
    })()
    p.finally(() => inflight.delete(key))
    inflight.set(key, p)
  }
  return p
}

/** Warm the cache for neighbouring sections so page turns don't wait. */
export function prefetchSections(sidecarId: number, indexes: number[]): void {
  for (const i of indexes) void loadSectionCandidates(sidecarId, i).catch(() => undefined)
}
