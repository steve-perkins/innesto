import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import Popover from '../reader/Popover'
import { selectCandidates, type Candidate } from '../reader/selection'
import { buildTextStream, sha256Hex } from '../reader/textstream'
import { applyLayout, bookTitle, createView, type Location, type TocItem, type View } from '../reader/view'
import { swapIdOf, unweave, weave } from '../reader/weave'
import { getBookFile, loadProgress, saveProgress } from '../store/cache'
import { useSettings } from '../store/settings'
import { loadSidecar, type SidecarStatus } from '../store/sidecar'
import { useVocab } from '../store/vocab'

type Status = { kind: 'loading'; text: string } | { kind: 'ready' } | { kind: 'error'; text: string }

interface PopoverState { candidate: Candidate; anchor: DOMRect }

export default function Reader() {
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const settings = useSettings()
  const vocab = useVocab()
  const host = useRef<HTMLDivElement>(null)
  const viewRef = useRef<View | null>(null)
  const saveTimer = useRef<number | undefined>(undefined)

  const [status, setStatus] = useState<Status>({ kind: 'loading', text: 'Opening…' })
  const [title, setTitle] = useState('')
  const [toc, setToc] = useState<TocItem[]>([])
  const [loc, setLoc] = useState<Location | null>(null)
  const [immersive, setImmersive] = useState(false)
  const [tocOpen, setTocOpen] = useState(false)
  const [sidecar, setSidecar] = useState<SidecarStatus | null>(null)
  const [popover, setPopover] = useState<PopoverState | null>(null)
  const [weaveInfo, setWeaveInfo] = useState<string>('')

  // Latest values reachable from long-lived event handlers.
  const settingsRef = useRef(settings); settingsRef.current = settings
  const sidecarRef = useRef(sidecar); sidecarRef.current = sidecar
  const popoverRef = useRef(popover); popoverRef.current = popover
  const vocabRef = useRef(vocab); vocabRef.current = vocab
  // Candidates currently woven into each loaded section, by id.
  const wovenRef = useRef(new Map<Document, Map<string, Candidate>>())

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
      case 'Escape': setTocOpen(false); setImmersive(false); setPopover(null); break
      default: return
    }
  }, [paging])

  // Weaving is async (hashing) and mutates the DOM, so passes on the same
  // document must not interleave: chain them per document.
  const weaveQueue = useRef(new WeakMap<Document, Promise<void>>())

  /** (Re)apply swaps to one section document using current settings. */
  const weaveDoc = useCallback((doc: Document, index: number): Promise<void> => {
    const prev = weaveQueue.current.get(doc) ?? Promise.resolve()
    const next = prev.then(() => weaveDocNow(doc, index)).catch((err) => console.error('Innesto weave failed', err))
    weaveQueue.current.set(doc, next)
    return next
  }, [])

  const weaveDocNow = async (doc: Document, index: number) => {
    const sc = sidecarRef.current
    const s = settingsRef.current
    if (!sc || sc.kind !== 'ready') return
    const section = sc.sections.get(index)
    if (!section) { unweave(doc); wovenRef.current.delete(doc); return }
    unweave(doc)
    const stream = buildTextStream(doc)
    const hash = await sha256Hex(stream.text)
    if (hash !== section.textHash) {
      console.warn(`Innesto: section ${index} text differs from sidecar; skipping`)
      setWeaveInfo('Text differs from sidecar for this section')
      return
    }
    const chosen = selectCandidates(section.candidates, {
      level: s.level, density: s.density, wordCount: section.wordCount,
      seed: `${sc.sidecar.bookId}:${index}:${s.level}:${s.density}`,
      known: vocabRef.current.known, learning: vocabRef.current.learning,
    })
    const result = weave(doc, chosen, stream)
    wovenRef.current.set(doc, new Map(chosen.map((c) => [c.id, c])))
    setWeaveInfo(`${result.applied} swaps · L${s.level} · D${s.density}${result.skipped ? ` · ${result.skipped} skipped` : ''}`)
  }

  const reweaveAll = useCallback(() => {
    const v = viewRef.current
    if (!v?.renderer) return
    for (const { doc, index } of v.renderer.getContents()) void weaveDoc(doc, index)
  }, [weaveDoc])

  // Open the book.
  useEffect(() => {
    let cancelled = false
    const view = createView()
    viewRef.current = view
    host.current?.replaceChildren(view)
    wovenRef.current = new Map()

    const onLoad = (e: Event) => {
      const { doc, index } = (e as CustomEvent<{ doc: Document; index: number }>).detail
      doc.addEventListener('keydown', onKey)
      doc.addEventListener('click', (ev) => {
        const target = ev.target as Element | null
        if (popoverRef.current) { setPopover(null); return }
        const swapId = swapIdOf(target)
        if (swapId) {
          const candidate = wovenRef.current.get(doc)?.get(swapId)
          const el = target?.closest('.innesto') as HTMLElement | null
          const frame = doc.defaultView?.frameElement as HTMLElement | null
          if (candidate && el && frame) {
            const r = el.getBoundingClientRect(), f = frame.getBoundingClientRect()
            setPopover({ candidate, anchor: new DOMRect(r.left + f.left, r.top + f.top, r.width, r.height) })
            if (candidate.targetLemmas?.length) vocabRef.current.lookup(settingsRef.current.targetLang, candidate.targetLemmas)
          }
          return
        }
        if (target?.closest('a, input, button, textarea, select, video, audio')) return
        // Measure against the visible page in top-window coordinates: the
        // section iframe is as wide as all of its pages and scrolled by the
        // paginator, so its own clientX/innerWidth are meaningless here.
        const frame = doc.defaultView?.frameElement
        const left = frame ? frame.getBoundingClientRect().left : 0
        const r = (left + ev.clientX) / window.innerWidth
        if (r < 0.2) paging('left')
        else if (r > 0.8) paging('right')
        else paging('toggle')
      })
      void weaveDoc(doc, index)
    }
    const onRelocate = (e: Event) => {
      const detail = (e as CustomEvent<Location>).detail
      setLoc(detail)
      setPopover(null)
      window.clearTimeout(saveTimer.current)
      saveTimer.current = window.setTimeout(() => {
        void saveProgress(id, detail.cfi ?? null, Number.isFinite(detail.fraction) ? detail.fraction : 0)
      }, 800)
    }

    ;(async () => {
      try {
        setStatus({ kind: 'loading', text: 'Downloading…' })
        const [blob, sc] = await Promise.all([
          getBookFile(id), loadSidecar(id, settingsRef.current.targetLang),
          vocabRef.current.load(settingsRef.current.targetLang),
        ])
        if (cancelled) return
        setSidecar(sc); sidecarRef.current = sc
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
        // Restore by overall fraction rather than CFI: CFIs are computed
        // against the live DOM, which weaving restructures (split text nodes,
        // extra spans), so a CFI saved from a woven page does not resolve
        // against the fresh one. Fractions are DOM-independent.
        await view.init({ showTextStart: true })
        if (cancelled) return
        if (saved.fraction > 0) await view.goToFraction(saved.fraction)
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
  }, [id, onKey, paging, weaveDoc])

  // Re-apply layout/theme when settings change; re-weave when weave settings change.
  useEffect(() => {
    if (status.kind === 'ready' && viewRef.current) applyLayout(viewRef.current, settings)
  }, [settings, status.kind])
  useEffect(() => {
    if (status.kind === 'ready') reweaveAll()
  }, [settings.level, settings.density, status.kind, reweaveAll])

  const fraction = Number.isFinite(loc?.fraction) ? (loc!.fraction as number) : 0
  const pct = Math.round(fraction * 100)
  const pageInfo = loc?.location ? `${loc.location.current + 1} / ${loc.location.total}` : ''
  const sidecarNote = sidecar?.kind === 'missing' ? 'No translations yet for this book (process it from the library).'
    : sidecar?.kind === 'error' ? `Translations unavailable: ${sidecar.message}` : null

  return (
    <div className={`reader${immersive ? ' immersive' : ''}`}>
      <header className="topbar">
        <button className="icon" onClick={() => navigate('/')} aria-label="Back to library" title="Library">‹</button>
        <h1 title={title}>{title}</h1>
        <LevelControls />
        <button className="icon" onClick={() => setTocOpen(true)} aria-label="Table of contents" title="Contents">☰</button>
        <Link to="/settings" state={{ from: `/read/${id}` }}><button className="icon" aria-label="Settings" title="Settings">⚙︎</button></Link>
      </header>

      <div ref={host} style={{ flex: 1, minHeight: 0, display: 'flex' }} />

      {status.kind === 'ready' && (
        <>
          <button className="page-arrow left" aria-label="Previous page" title="Previous page (←)"
                  onClick={() => paging('left')}>‹</button>
          <button className="page-arrow right" aria-label="Next page" title="Next page (→)"
                  onClick={() => paging('right')}>›</button>
        </>
      )}

      {status.kind !== 'ready' && (
        <div className="status">
          <p className={status.kind === 'error' ? 'error' : undefined}>{status.text}</p>
        </div>
      )}
      {!immersive && <div className="weave-info">{sidecarNote ?? weaveInfo}</div>}

      <footer className="bottombar">
        <span className="muted" style={{ minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '40%' }}>
          {loc?.tocItem?.label ?? ''}
        </span>
        <input type="range" min={0} max={1} step={0.001} value={fraction}
               aria-label="Position in book"
               onChange={(e) => void viewRef.current?.goToFraction(Number(e.target.value))} />
        <span className="muted">{pageInfo || `${pct}%`}</span>
      </footer>

      {popover && (
        <Popover candidate={popover.candidate} anchor={popover.anchor}
                 targetLang={settings.targetLang} onClose={() => setPopover(null)} />
      )}

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

/** Compact Level / Density steppers in the reader toolbar. */
function LevelControls() {
  const { level, density, set } = useSettings()
  return (
    <div className="level-controls" title="Level and density of target-language swaps">
      <button className="icon" aria-label="Lower level" disabled={level <= 1} onClick={() => set({ level: level - 1 })}>−</button>
      <span>L{level}</span>
      <button className="icon" aria-label="Raise level" disabled={level >= 5} onClick={() => set({ level: level + 1 })}>+</button>
      <button className="icon" aria-label="Fewer swaps" disabled={density <= 1} onClick={() => set({ density: Math.max(1, density - 2) })}>−</button>
      <span>D{density}</span>
      <button className="icon" aria-label="More swaps" disabled={density >= 40} onClick={() => set({ density: Math.min(40, density + 2) })}>+</button>
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
