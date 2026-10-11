import { describe, expect, it } from 'vitest'
import { buildTextStream, rangeFor } from './textstream'

const XHTML = `<?xml version="1.0"?><html xmlns="http://www.w3.org/1999/xhtml"><head><title>T</title></head>
<body><p>Hello<!-- c --> world<script>var x = 1;</script> again.</p><div>Two<br/>lines</div></body></html>`

describe('buildTextStream', () => {
  it('matches the server algorithm', () => {
    const doc = new DOMParser().parseFromString(XHTML, 'application/xhtml+xml')
    const ts = buildTextStream(doc)
    expect(ts.text).toBe('Hello world again.Twolines')
    expect(ts.segments.map((s) => s.node.data)).toEqual(['Hello', ' world', ' again.', 'Two', 'lines'])
  })

  it('builds ranges across inline elements', () => {
    const doc = new DOMParser().parseFromString(
      '<html xmlns="http://www.w3.org/1999/xhtml"><body><p>He reads <em>very</em> slowly.</p></body></html>',
      'application/xhtml+xml')
    const ts = buildTextStream(doc)
    const start = ts.text.indexOf('very slowly')
    const range = rangeFor(ts, start, start + 'very slowly'.length)!
    expect(range.toString()).toBe('very slowly')
    const whole = rangeFor(ts, 0, ts.text.length)!
    expect(whole.toString()).toBe('He reads very slowly.')
  })
})
