// IndexedDB cache (Dexie) so books already opened keep working offline and
// re-opening a book does not re-download it.
import Dexie, { type EntityTable } from 'dexie'
import { api } from '../api/client'

interface CachedFile { id: string; blob: Blob; savedAt: number }
interface CachedProgress { id: string; cfi: string | null; fraction: number; updatedAt: number }

const db = new Dexie('innesto') as Dexie & {
  files: EntityTable<CachedFile, 'id'>
  progress: EntityTable<CachedProgress, 'id'>
}
db.version(1).stores({ files: 'id', progress: 'id' })

export async function getBookFile(id: string): Promise<Blob> {
  const cached = await db.files.get(id).catch(() => undefined)
  if (cached) return cached.blob
  const res = await fetch(api.bookFileUrl(id))
  if (!res.ok) throw new Error(`Could not download book (${res.status})`)
  const blob = await res.blob()
  await db.files.put({ id, blob, savedAt: Date.now() }).catch(() => undefined)
  return blob
}

export async function forgetBook(id: string): Promise<void> {
  await Promise.all([db.files.delete(id), db.progress.delete(id)]).catch(() => undefined)
}

/** Last known position: server wins when reachable, local copy otherwise. */
export async function loadProgress(id: string): Promise<{ cfi: string | null; fraction: number }> {
  try {
    const p = await api.getProgress(id)
    return { cfi: p.cfi, fraction: p.fraction }
  } catch {
    const local = await db.progress.get(id).catch(() => undefined)
    return local ?? { cfi: null, fraction: 0 }
  }
}

export async function saveProgress(id: string, cfi: string | null, fraction: number): Promise<void> {
  await db.progress.put({ id, cfi, fraction, updatedAt: Date.now() }).catch(() => undefined)
  try { await api.putProgress(id, cfi, fraction) } catch { /* offline: local copy kept */ }
}
