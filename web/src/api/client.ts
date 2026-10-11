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
}

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
  getToc: (id: string) => request<TocEntry[]>(`/api/books/${id}/toc`),
  getProgress: (id: string) => request<ReadingPosition>(`/api/books/${id}/progress`),
  putProgress: (id: string, cfi: string | null, fraction: number) =>
    request<ReadingPosition>(`/api/books/${id}/progress`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cfi, fraction }),
    }),
}
