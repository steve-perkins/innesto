// Wrapper around the vendored foliate-js <foliate-view> custom element.
import '../../vendor/foliate-js/view.js'
import type { FoliateBook, View } from '../../vendor/foliate-js/view.js'
import type { Settings } from '../store/settings'

export type { Location, TocItem, View } from '../../vendor/foliate-js/view.js'

export function createView(): View {
  return document.createElement('foliate-view') as View
}

function asText(value: unknown): string {
  if (typeof value === 'string') return value
  if (Array.isArray(value)) return value.map(asText).filter(Boolean).join(', ')
  if (value && typeof value === 'object') {
    const o = value as Record<string, unknown>
    if (typeof o.name === 'string') return o.name
    const first = Object.values(o).find((v) => typeof v === 'string')
    return typeof first === 'string' ? first : ''
  }
  return ''
}

export function bookTitle(book: FoliateBook | undefined, fallback = 'Untitled'): string {
  return asText(book?.metadata?.title) || fallback
}

function cssVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}

/** CSS injected into every book section. Colors follow the app theme. */
export function bookCss(s: Settings): string {
  const fg = cssVar('--book-fg')
  const link = cssVar('--book-link')
  return `
    @namespace epub "http://www.idpf.org/2007/ops";
    html { color: ${fg}; font-size: ${s.fontSize}% !important; }
    body { color: inherit; background: transparent !important; }
    p, li, dd, blockquote { line-height: ${s.lineHeight} !important; }
    a:link, a:visited { color: ${link}; }
    /* Diglot-weave swaps (phase 3). */
    .innesto {
      color: ${s.swapColor};
      cursor: pointer;
      text-decoration: underline dotted;
      text-decoration-thickness: 1px;
      text-underline-offset: 3px;
      border-radius: 3px;
    }
    .innesto:hover { background: color-mix(in srgb, ${s.swapColor} 12%, transparent); }
  `
}

export function applyLayout(view: View, s: Settings): void {
  const r = view.renderer
  if (!r) return
  r.setAttribute('flow', s.flow)
  r.setAttribute('gap', '6%')
  r.setAttribute('margin', '56px')
  r.setAttribute('max-inline-size', '760px')
  r.setAttribute('max-column-count', '2')
  r.setAttribute('animated', '')
  r.setStyles?.(bookCss(s))
}
