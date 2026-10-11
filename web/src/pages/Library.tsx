import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, type Book } from '../api/client'
import { forgetBook } from '../store/cache'
import { useSettings } from '../store/settings'

function StatusBadge({ book, lang }: { book: Book; lang: string }) {
  const job = book.job
  if (job && (job.status === 'queued' || job.status === 'running')) {
    const pct = job.total ? Math.round((job.progress / job.total) * 100) : 0
    return <span className="badge busy">Processing {job.status === 'running' ? `${pct}%` : '…'}</span>
  }
  if (book.sidecar_langs.includes(lang)) return <span className="badge ok">Ready · {lang.toUpperCase()}</span>
  if (job?.status === 'error') return <span className="badge err" title={job.error ?? ''}>Failed</span>
  return <span className="badge">Not processed</span>
}

export default function Library() {
  const [books, setBooks] = useState<Book[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [menuFor, setMenuFor] = useState<string | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)
  const sidecarInput = useRef<HTMLInputElement>(null)
  const sidecarTarget = useRef<string | null>(null)
  const navigate = useNavigate()
  const targetLang = useSettings((s) => s.targetLang)

  const refresh = useCallback(async () => {
    try { setBooks(await api.listBooks()); setError(null) }
    catch (e) { setError(`Could not load library: ${(e as Error).message}`) }
  }, [])
  useEffect(() => { void refresh() }, [refresh])

  // Close the card menu on outside click or Escape.
  useEffect(() => {
    if (!menuFor) return
    const close = (e: Event) => {
      if (e instanceof KeyboardEvent && e.key !== 'Escape') return
      if (e instanceof MouseEvent && (e.target as Element | null)?.closest('.menu, .menu-button')) return
      setMenuFor(null)
    }
    window.addEventListener('click', close)
    window.addEventListener('keydown', close)
    return () => { window.removeEventListener('click', close); window.removeEventListener('keydown', close) }
  }, [menuFor])

  // Poll while any book is being processed.
  const processing = books?.some((b) => b.job && (b.job.status === 'queued' || b.job.status === 'running')) ?? false
  useEffect(() => {
    if (!processing) return
    const t = window.setInterval(() => void refresh(), 2000)
    return () => window.clearInterval(t)
  }, [processing, refresh])

  async function onFiles(files: FileList | null) {
    if (!files?.length) return
    setBusy(true)
    try {
      for (const file of Array.from(files)) await api.uploadBook(file)
      await refresh()
    } catch (e) { setError(`Upload failed: ${(e as Error).message}`) }
    finally { setBusy(false); if (fileInput.current) fileInput.current.value = '' }
  }

  async function onSidecarFile(files: FileList | null) {
    const bookId = sidecarTarget.current
    if (!files?.length || !bookId) return
    try { await api.importSidecar(bookId, files[0]); await refresh() }
    catch (e) { setError(`Sidecar import failed: ${(e as Error).message}`) }
    finally { if (sidecarInput.current) sidecarInput.current.value = '' }
  }

  async function process(book: Book) {
    try { await api.startJob(book.id, targetLang); await refresh() }
    catch (e) { setError(`Could not start processing: ${(e as Error).message}`) }
  }

  async function remove(book: Book) {
    if (!confirm(`Remove "${book.title}" from your library?`)) return
    try { await api.deleteBook(book.id); await forgetBook(book.id); await refresh() }
    catch (e) { setError(`Delete failed: ${(e as Error).message}`) }
  }

  return (
    <>
      <header className="topbar">
        <Link to="/" className="brand">Innesto</Link>
        <h1 className="muted" style={{ fontWeight: 400 }}>Library</h1>
        <input ref={fileInput} type="file" accept=".epub,application/epub+zip" multiple hidden
               onChange={(e) => void onFiles(e.target.files)} />
        <input ref={sidecarInput} type="file" accept=".json,application/json" hidden
               onChange={(e) => void onSidecarFile(e.target.files)} />
        <button className="primary" disabled={busy} onClick={() => fileInput.current?.click()}>
          {busy ? 'Uploading…' : 'Add EPUB'}
        </button>
        <Link to="/vocabulary"><button title="Vocabulary">Vocabulary</button></Link>
        <Link to="/settings"><button className="icon" title="Settings" aria-label="Settings">⚙︎</button></Link>
      </header>
      <main className="page"
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => { e.preventDefault(); void onFiles(e.dataTransfer.files) }}>
        {error && <p className="error">{error}</p>}
        {books === null && !error && <p className="muted">Loading…</p>}
        {books?.length === 0 && (
          <div className="empty">
            <p>Your library is empty.</p>
            <p>Add an EPUB with the button above, or drop one here.</p>
          </div>
        )}
        {books && books.length > 0 && (
          <div className="grid">
            {books.map((b) => {
              const pending = b.job && (b.job.status === 'queued' || b.job.status === 'running')
              return (
                <article className={`card${menuFor === b.id ? ' menu-open' : ''}`} key={b.id}>
                  <div className="cover" onClick={() => navigate(`/read/${b.id}`)} role="button" tabIndex={0}
                       onKeyDown={(e) => e.key === 'Enter' && navigate(`/read/${b.id}`)}>
                    {b.has_cover
                      ? <img src={api.coverUrl(b.id)} alt="" loading="lazy" />
                      : <div className="placeholder">{b.title}</div>}
                  </div>
                  <div className="meta">
                    <div className="title" title={b.title}>{b.title}</div>
                    {b.author && <div className="muted">{b.author}</div>}
                    <div><StatusBadge book={b} lang={targetLang} /></div>
                    <div className="actions">
                      <button onClick={() => navigate(`/read/${b.id}`)}>Read</button>
                      {!pending && !b.sidecar_langs.includes(targetLang) && (
                        <button onClick={() => void process(b)} title="Generate translations for this book">Process</button>
                      )}
                      <button className="icon menu-button" title="More" aria-label="More actions"
                              aria-expanded={menuFor === b.id}
                              onClick={() => setMenuFor(menuFor === b.id ? null : b.id)}>⋯</button>
                    </div>
                    {menuFor === b.id && (
                      <div className="menu" role="menu">
                        <button role="menuitem" onClick={() => { setMenuFor(null); sidecarTarget.current = b.id; sidecarInput.current?.click() }}>Import sidecar…</button>
                        {!pending && b.sidecar_langs.includes(targetLang) && (
                          <button role="menuitem" onClick={() => { setMenuFor(null); void process(b) }}>Re-process</button>
                        )}
                        <button role="menuitem" className="danger" onClick={() => { setMenuFor(null); void remove(b) }}>Remove</button>
                      </div>
                    )}
                  </div>
                </article>
              )
            })}
          </div>
        )}
      </main>
    </>
  )
}
