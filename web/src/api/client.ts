// Thin typed client for the Innesto API. All paths are relative so the same
// build works behind the Vite dev proxy and behind the production server.

export interface Book {
  id: string
  title: string
  author: string | null
  language: string | null
  filename: string
  size: number
  section_count: number
  has_cover: boolean
  added_at: string
  sidecar_langs: string[]
  job: Job | null
}

export interface Job {
  id: number
  book_id: string
  target_lang: string
  status: 'queued' | 'running' | 'done' | 'error'
  progress: number
  total: number
  error: string | null
  sidecar_id: number | null
  created_at: string
  updated_at: string
}

export interface SidecarRow {
  id: number
  book_id: string
  target_lang: string
  generator_name: string
  generator_version: string
  engine: string | null
  active: boolean
  candidate_count: number
  created_at: string
}

export interface VocabEntry {
  id: number
  lang: string
  lemma: string
  status: 'known' | 'learning'
  lookups: number
  last_seen: string
}

export interface VocabSummary { lang: string; known: string[]; learning: string[] }

export interface ReadingPosition {
  book_id: string
  cfi: string | null
  fraction: number
  updated_at: string
}

export interface TocEntry { label: string; href: string; subitems: TocEntry[] }

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init)
  if (!res.ok) {
    let detail = res.statusText
    try { detail = (await res.json()).detail ?? detail } catch { /* not json */ }
    throw new Error(`${res.status}: ${detail}`)
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

export const api = {
  health: () => request<{ status: string; version: string }>('/api/health'),
  listBooks: () => request<Book[]>('/api/books'),
  getBook: (id: string) => request<Book>(`/api/books/${id}`),
  uploadBook: (file: File) => {
    const body = new FormData()
    body.append('file', file)
    return request<Book>('/api/books', { method: 'POST', body })
  },
  deleteBook: (id: string) => request<void>(`/api/books/${id}`, { method: 'DELETE' }),
  bookFileUrl: (id: string) => `/api/books/${id}/file`,
  coverUrl: (id: string) => `/api/books/${id}/cover`,
  startJob: (id: string, targetLang: string) =>
    request<Job>(`/api/books/${id}/jobs?target_lang=${encodeURIComponent(targetLang)}`, { method: 'POST' }),
  listSidecars: (id: string) => request<SidecarRow[]>(`/api/books/${id}/sidecars`),
  importSidecar: (id: string, file: File) => {
    const body = new FormData()
    body.append('file', file)
    return request<SidecarRow>(`/api/books/${id}/sidecars`, { method: 'POST', body })
  },
  activateSidecar: (sidecarId: number) => request<SidecarRow>(`/api/sidecars/${sidecarId}/activate`, { method: 'POST' }),
  vocabSummary: (lang: string) => request<VocabSummary>(`/api/vocab/summary?lang=${encodeURIComponent(lang)}`),
  listVocab: (lang: string) => request<VocabEntry[]>(`/api/vocab?lang=${encodeURIComponent(lang)}`),
  upsertVocab: (lang: string, lemma: string, status?: 'known' | 'learning', lookup = false) =>
    request<VocabEntry>('/api/vocab', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ lang, lemma, status: status ?? null, lookup }),
    }),
  deleteVocab: (lang: string, lemma: string) =>
    request<void>(`/api/vocab/${encodeURIComponent(lang)}/${encodeURIComponent(lemma)}`, { method: 'DELETE' }),
  vocabCsvUrl: (lang: string) => `/api/vocab/export.csv?lang=${encodeURIComponent(lang)}`,
  getToc: (id: string) => request<TocEntry[]>(`/api/books/${id}/toc`),
  getProgress: (id: string) => request<ReadingPosition>(`/api/books/${id}/progress`),
  putProgress: (id: string, cfi: string | null, fraction: number) =>
    request<ReadingPosition>(`/api/books/${id}/progress`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cfi, fraction }),
    }),
}
