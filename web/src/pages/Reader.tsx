import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { applyLayout, bookTitle, createView, type Location, type TocItem, type View } from '../reader/view'
import { getBookFile, loadProgress, saveProgress } from '../store/cache'
import { useSettings } from '../store/settings'

type Status = { kind: 'loading'; text: string } | { kind: 'ready' } | { kind: 'error'; text: string }

export default function Reader() {
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const settings = useSettings()
  const host = useRef<HTMLDivElement>(null)
  const viewRef = useRef<View | null>(null)
  const saveTimer = useRef<number | undefined>(undefined)

  const [status, setStatus] = useState<Status>({ kind: 'loading', text: 'Opening…' })
  const [title, setTitle] = useState('')
  const [toc, setToc] = useState<TocItem[]>([])
  const [loc, setLoc] = useState<Location | null>(null)
  const [immersive, setImmersive] = useState(false)
  const [tocOpen, setTocOpen] = useState(false)

  // Keep the latest settings reachable from event handlers without re-binding.
  const settingsRef = useRef(settings)
  settingsRef.current = settings

  const paging = useCallback((dir: 'left' | 'right' | 'toggle') => {
    const v = viewRef.current
    if (!v) return
    if (dir === 'left') void v.goLeft()
    else if (dir === 'right') void v.goRight()
    else setImmersive((x) => !x)
  }, [])

  const onKey = useCallback((e: KeyboardEvent) => {
    if ((e.target as HTMLElement | null)?.tagName === 'INPUT') return
    switch (e.key) {
      case 'ArrowLeft': case 'h': paging('left'); break
      case 'ArrowRight': case 'l': paging('right'); break
      case 'PageUp': void viewRef.current?.prev(); break
      case 'PageDown': case ' ': e.preventDefault(); void viewRef.current?.next(); break
      case 'Escape': setTocOpen(false); setImmersive(false); break
      default: return
    }
  }, [paging])

  // Open the book.
  useEffect(() => {
    let cancelled = false
    const view = createView()
    viewRef.current = view
    host.current?.replaceChildren(view)

    const onLoad = (e: Event) => {
      const { doc } = (e as CustomEvent<{ doc: Document; index: number }>).detail
      doc.addEventListener('keydown', onKey)
      doc.addEventListener('click', (ev) => {
        const target = ev.target as Element | null
        if (target?.closest('a, .innesto, input, button, textarea, select, video, audio')) return
        const width = doc.defaultView?.innerWidth ?? 1
        const r = ev.clientX / width
        if (r < 0.22) paging('left')
        else if (r > 0.78) paging('right')
        else paging('toggle')
      })
    }
    const onRelocate = (e: Event) => {
      const detail = (e as CustomEvent<Location>).detail
      setLoc(detail)
      window.clearTimeout(saveTimer.current)
      saveTimer.current = window.setTimeout(() => {
        void saveProgress(id, detail.cfi ?? null, detail.fraction ?? 0)
      }, 800)
    }

    ;(async () => {
      try {
        setStatus({ kind: 'loading', text: 'Downloading…' })
        const blob = await getBookFile(id)
        if (cancelled) return
        setStatus({ kind: 'loading', text: 'Opening…' })
        view.addEventListener('load', onLoad)
        view.addEventListener('relocate', onRelocate)
        await view.open(new File([blob], 'book.epub', { type: 'application/epub+zip' }))
        if (cancelled) return
        setTitle(bookTitle(view.book))
        setToc(view.book.toc ?? [])
        applyLayout(view, settingsRef.current)
        const saved = await loadProgress(id)
        if (cancelled) return
        await view.init({ lastLocation: saved.cfi ?? undefined, showTextStart: true })
        if (!cancelled) setStatus({ kind: 'ready' })
      } catch (err) {
        console.error(err)
        if (!cancelled) setStatus({ kind: 'error', text: (err as Error).message })
      }
    })()

    window.addEventListener('keydown', onKey)
    return () => {
      cancelled = true
      window.removeEventListener('keydown', onKey)
      window.clearTimeout(saveTimer.current)
      view.removeEventListener('load', onLoad)
      view.removeEventListener('relocate', onRelocate)
      try { view.close() } catch { /* not opened */ }
      view.remove()
      if (viewRef.current === view) viewRef.current = null
    }
  }, [id, onKey, paging])

  // Re-apply layout/theme when settings change.
  useEffect(() => {
    if (status.kind === 'ready' && viewRef.current) applyLayout(viewRef.current, settings)
  }, [settings, status.kind])

  const pct = Math.round((loc?.fraction ?? 0) * 100)
  const pageInfo = loc?.location ? `${loc.location.current + 1} / ${loc.location.total}` : ''

  return (
    <div className={`reader${immersive ? ' immersive' : ''}`}>
      <header className="topbar">
        <button className="icon" onClick={() => navigate('/')} aria-label="Back to library" title="Library">‹</button>
        <h1 title={title}>{title}</h1>
        <button className="icon" onClick={() => setTocOpen(true)} aria-label="Table of contents" title="Contents">☰</button>
        <Link to="/settings"><button className="icon" aria-label="Settings" title="Settings">⚙︎</button></Link>
      </header>

      <div ref={host} style={{ flex: 1, minHeight: 0, display: 'flex' }} />

      {status.kind !== 'ready' && (
        <div className="status">
          <p className={status.kind === 'error' ? 'error' : undefined}>{status.text}</p>
        </div>
      )}

      <footer className="bottombar">
        <span className="muted" style={{ minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '40%' }}>
          {loc?.tocItem?.label ?? ''}
        </span>
        <input type="range" min={0} max={1} step={0.001} value={loc?.fraction ?? 0}
               aria-label="Position in book"
               onChange={(e) => void viewRef.current?.goToFraction(Number(e.target.value))} />
        <span className="muted">{pageInfo || `${pct}%`}</span>
      </footer>

      {tocOpen && (
        <>
          <div className="drawer-backdrop" onClick={() => setTocOpen(false)} />
          <nav className="drawer toc" aria-label="Table of contents">
            <h2>Contents</h2>
            {toc.length === 0 && <p className="muted">This book has no table of contents.</p>}
            <TocList items={toc} currentHref={loc?.tocItem?.href}
                     onPick={(href) => { setTocOpen(false); void viewRef.current?.goTo(href) }} />
          </nav>
        </>
      )}
    </div>
  )
}

function TocList({ items, currentHref, onPick }: {
  items: TocItem[]; currentHref?: string; onPick: (href: string) => void
}) {
  return (
    <ol>
      {items.map((item, i) => (
        <li key={`${item.href}-${i}`}>
          <button className={item.href === currentHref ? 'current' : undefined}
                  onClick={() => onPick(item.href)}>{item.label || '(untitled)'}</button>
          {item.subitems && item.subitems.length > 0 && (
            <TocList items={item.subitems} currentHref={currentHref} onPick={onPick} />
          )}
        </li>
      ))}
    </ol>
  )
}
