import { describe, expect, it } from 'vitest'
import { selectCandidates, type Candidate } from './selection'

function cand(id: string, start: number, end: number, kind: Candidate['kind'], level: number, lemma = id): Candidate {
  return { id, start, end, text: id, translation: `t:${id}`, kind, level, difficulty: level / 5,
           lemmas: [lemma], targetLemmas: [`x${lemma}`], sentence: { start: Math.floor(start / 100) * 100, end: Math.floor(start / 100) * 100 + 99 } }
}

const pool: Candidate[] = []
for (let i = 0; i < 40; i++) {
  const base = i * 100
  pool.push(cand(`w${i}`, base + 5, base + 10, 'word', 1))
  pool.push(cand(`np${i}`, base + 20, base + 30, 'np', 1 + (i % 2)))
  pool.push(cand(`vp${i}`, base + 40, base + 50, 'vp', 2))
  pool.push(cand(`cl${i}`, base + 20, base + 60, 'clause', 4))
  pool.push(cand(`s${i}`, base, base + 90, 'sentence', 5))
}

describe('selectCandidates', () => {
  it('respects level and never overlaps', () => {
    const picked = selectCandidates(pool, { level: 2, density: 10, wordCount: 1000, seed: 'a' })
    expect(picked.every((c) => c.level <= 2)).toBe(true)
    for (let i = 1; i < picked.length; i++) expect(picked[i].start).toBeGreaterThanOrEqual(picked[i - 1].end)
    expect(picked.length).toBeLessThanOrEqual(100)
    expect(picked.length).toBeGreaterThan(0)
  })

  it('hits the density target when enough candidates exist', () => {
    const picked = selectCandidates(pool, { level: 3, density: 5, wordCount: 1000, seed: 'b' })
    expect(picked.length).toBe(50)
  })

  it('is deterministic per seed and varies across seeds', () => {
    const a1 = selectCandidates(pool, { level: 3, density: 6, wordCount: 1000, seed: 'same' }).map((c) => c.id)
    const a2 = selectCandidates(pool, { level: 3, density: 6, wordCount: 1000, seed: 'same' }).map((c) => c.id)
    const b = selectCandidates(pool, { level: 3, density: 6, wordCount: 1000, seed: 'other' }).map((c) => c.id)
    expect(a1).toEqual(a2)
    expect(a1).not.toEqual(b)
  })

  it('prefers learning lemmas and avoids known ones', () => {
    const learning = new Set(['xnp2'])
    const known = new Set(pool.filter((c) => c.kind === 'word').map((c) => `x${c.lemmas[0]}`))
    const picked = selectCandidates(pool, { level: 1, density: 1, wordCount: 1000, seed: 'c', learning, known })
    expect(picked.some((c) => c.id === 'np2')).toBe(true)
    expect(picked.filter((c) => c.kind === 'word').length).toBe(0)
  })

  it('keeps one swap per sentence at low levels', () => {
    const picked = selectCandidates(pool, { level: 1, density: 40, wordCount: 1000, seed: 'd' })
    const sentences = new Set(picked.map((c) => c.sentence!.start))
    expect(sentences.size).toBe(picked.length)
  })
})
