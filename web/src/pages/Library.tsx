import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, type Book } from '../api/client'
import { forgetBook } from '../store/cache'

export default function Library() {
  const [books, setBooks] = useState<Book[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const fileInput = useRef<HTMLInputElement>(null)
  const navigate = useNavigate()

  const refresh = useCallback(async () => {
    try { setBooks(await api.listBooks()); setError(null) }
    catch (e) { setError(`Could not load library: ${(e as Error).message}`) }
  }, [])
  useEffect(() => { void refresh() }, [refresh])

  async function onFiles(files: FileList | null) {
    if (!files?.length) return
    setBusy(true)
    try {
      for (const file of Array.from(files)) await api.uploadBook(file)
      await refresh()
    } catch (e) { setError(`Upload failed: ${(e as Error).message}`) }
    finally { setBusy(false); if (fileInput.current) fileInput.current.value = '' }
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
        <button className="primary" disabled={busy} onClick={() => fileInput.current?.click()}>
          {busy ? 'Uploading…' : 'Add EPUB'}
        </button>
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
            {books.map((b) => (
              <article className="card" key={b.id}>
                <div className="cover" onClick={() => navigate(`/read/${b.id}`)} role="button" tabIndex={0}
                     onKeyDown={(e) => e.key === 'Enter' && navigate(`/read/${b.id}`)}>
                  {b.has_cover
                    ? <img src={api.coverUrl(b.id)} alt="" loading="lazy" />
                    : <div className="placeholder">{b.title}</div>}
                </div>
                <div className="meta">
                  <div className="title" title={b.title}>{b.title}</div>
                  {b.author && <div className="muted">{b.author}</div>}
                  <div className="actions">
                    <button onClick={() => navigate(`/read/${b.id}`)}>Read</button>
                    <button className="danger" onClick={() => void remove(b)}>Remove</button>
                  </div>
                </div>
              </article>
            ))}
          </div>
        )}
      </main>
    </>
  )
}
