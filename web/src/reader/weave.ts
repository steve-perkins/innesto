// Applies selected candidates to a section document: wraps each span's text
// in <span class="innesto"> showing the translation, keeping the original
// content so the swap can be undone when Level/Density change.
import type { Candidate } from './selection'
import { buildTextStream, rangeFor, type TextStream } from './textstream'

export const SWAP_CLASS = 'innesto'
const ATTR_ID = 'data-innesto-id'

interface Applied {
  span: HTMLElement
  original: DocumentFragment
}

const state = new WeakMap<Document, Applied[]>()

export interface WeaveResult { applied: number; skipped: number }

/** Remove all swaps from `doc`, restoring the original text nodes. */
export function unweave(doc: Document): void {
  const applied = state.get(doc)
  if (!applied) return
  for (const { span, original } of applied.reverse()) {
    span.replaceWith(original)
  }
  state.delete(doc)
  doc.body.normalize()
}

/** Apply `chosen` (non-overlapping, sorted) to `doc`. Returns counts. */
export function weave(doc: Document, chosen: Candidate[], stream?: TextStream): WeaveResult {
  unweave(doc)
  const ts = stream ?? buildTextStream(doc)
  const applied: Applied[] = []
  let skipped = 0
  // Apply back to front so earlier offsets stay valid while nodes are split.
  for (const c of [...chosen].sort((a, b) => b.start - a.start)) {
    if (!c.translation) { skipped++; continue }
    if (ts.text.slice(c.start, c.end) !== c.text) { skipped++; continue }
    const range = rangeFor(ts, c.start, c.end)
    if (!range) { skipped++; continue }
    const original = range.extractContents()
    const span = doc.createElement('span')
    span.className = SWAP_CLASS
    span.setAttribute(ATTR_ID, c.id)
    span.setAttribute('lang', '')
    span.textContent = c.translation
    range.insertNode(span)
    applied.push({ span, original })
  }
  state.set(doc, applied)
  return { applied: applied.length, skipped }
}

export function swapIdOf(target: EventTarget | null): string | null {
  const el = (target as Element | null)?.closest?.(`.${SWAP_CLASS}`)
  return el?.getAttribute(ATTR_ID) ?? null
}
