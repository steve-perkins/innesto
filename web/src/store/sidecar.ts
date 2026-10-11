// Sidecar loading with an IndexedDB copy for offline reading.
import Dexie, { type EntityTable } from 'dexie'
import type { Candidate } from '../reader/selection'
import { authFetch } from './auth'

export interface SidecarSection {
  index: number
  href: string
  textHash: string
  wordCount: number
  candidates: Candidate[]
}

export interface Sidecar {
  schemaVersion: 1
  bookId: string
  sourceLang: string
  targetLang: string
  generator: { name: string; version: string; engine?: string; createdAt: string }
  sections: SidecarSection[]
}

interface CachedSidecar { key: string; sidecar: Sidecar; sidecarId: string | null; savedAt: number }

const db = new Dexie('innesto-sidecars') as Dexie & { sidecars: EntityTable<CachedSidecar, 'key'> }
db.version(1).stores({ sidecars: 'key' })

export type SidecarStatus =
  | { kind: 'ready'; sidecar: Sidecar; sections: Map<number, SidecarSection> }
  | { kind: 'missing' }
  | { kind: 'error'; message: string }

export async function loadSidecar(bookId: string, lang: string): Promise<SidecarStatus> {
  const key = `${bookId}:${lang}`
  try {
    const res = await authFetch(`/api/books/${bookId}/sidecars/active?lang=${encodeURIComponent(lang)}`)
    if (res.status === 404) {
      await db.sidecars.delete(key).catch(() => undefined)
      return { kind: 'missing' }
    }
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const sidecar = (await res.json()) as Sidecar
    await db.sidecars.put({ key, sidecar, sidecarId: res.headers.get('X-Sidecar-Id'), savedAt: Date.now() })
      .catch(() => undefined)
    return ready(sidecar)
  } catch (err) {
    const cached = await db.sidecars.get(key).catch(() => undefined)
    if (cached) return ready(cached.sidecar)
    return { kind: 'error', message: (err as Error).message }
  }
}

function ready(sidecar: Sidecar): SidecarStatus {
  return { kind: 'ready', sidecar, sections: new Map(sidecar.sections.map((s) => [s.index, s])) }
}
