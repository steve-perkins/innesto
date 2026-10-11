// Client mirror of api/innesto/epub/textstream.py. The two must produce the
// same string for the same section, because sidecar offsets index this stream.
//
// Rules: every text node under <body> in document order, verbatim; nothing
// from script/style/template/svg/math subtrees; comments contribute nothing.

const SKIP = new Set(['script', 'style', 'template', 'svg', 'math'])

export interface TextSegment { node: Text; start: number; end: number }

export interface TextStream {
  text: string
  segments: TextSegment[]
}

export function buildTextStream(doc: Document): TextStream {
  const body = doc.body ?? doc.documentElement
  const segments: TextSegment[] = []
  const parts: string[] = []
  let pos = 0

  const walk = (node: Node) => {
    if (node.nodeType === Node.TEXT_NODE) {
      const data = (node as Text).data
      if (data.length) {
        segments.push({ node: node as Text, start: pos, end: pos + data.length })
        parts.push(data)
        pos += data.length
      }
      return
    }
    if (node.nodeType !== Node.ELEMENT_NODE) return
    const name = (node as Element).localName.toLowerCase()
    if (SKIP.has(name)) return
    for (let child = node.firstChild; child; child = child.nextSibling) walk(child)
  }
  walk(body)
  return { text: parts.join(''), segments }
}

export async function sha256Hex(text: string): Promise<string> {
  const bytes = new TextEncoder().encode(text)
  const digest = await crypto.subtle.digest('SHA-256', bytes)
  return 'sha256:' + Array.from(new Uint8Array(digest)).map((b) => b.toString(16).padStart(2, '0')).join('')
}

/** Locate a stream offset as (text node, offset within node). `end` picks the
 * segment whose range ends at the offset when it lies on a boundary. */
export function locate(stream: TextStream, offset: number, end = false): { node: Text; offset: number } | null {
  const segs = stream.segments
  let lo = 0, hi = segs.length - 1
  while (lo <= hi) {
    const mid = (lo + hi) >> 1
    const s = segs[mid]
    if (offset < s.start || (offset === s.start && end && mid > 0)) hi = mid - 1
    else if (offset > s.end || (offset === s.end && !end && mid < segs.length - 1)) lo = mid + 1
    else return { node: s.node, offset: offset - s.start }
  }
  return null
}

/** Build a DOM Range for [start, end) in the stream. */
export function rangeFor(stream: TextStream, start: number, end: number): Range | null {
  const a = locate(stream, start, false)
  const b = locate(stream, end, true)
  if (!a || !b) return null
  const range = a.node.ownerDocument.createRange()
  range.setStart(a.node, a.offset)
  range.setEnd(b.node, b.offset)
  return range
}
