// Pure selection of which sidecar candidates to show, given the user's Level
// and Density. Deterministic for a given seed so a page looks the same each
// time it is rendered.

export type Kind = 'word' | 'np' | 'vp' | 'pp' | 'clause' | 'sentence'

export interface Candidate {
  id: string
  start: number
  end: number
  text: string
  translation: string | null
  kind: Kind
  level: number
  difficulty: number
  lemmas: string[]
  targetLemmas?: string[]
  sentence?: { start: number; end: number }
}

export interface SelectionOptions {
  level: number              // 1..5
  density: number            // desired swaps per 100 words
  wordCount: number
  seed: string
  /** Target-language lemmas the user already knows: strongly de-prioritised. */
  known?: Set<string>
  /** Lemmas the user is actively learning: prioritised. */
  learning?: Set<string>
}

const KIND_ORDER: Record<Kind, number> = { word: 0, np: 1, vp: 2, pp: 3, clause: 4, sentence: 5 }

// Small fast string hash -> 32-bit seed, then mulberry32 PRNG.
function hashSeed(s: string): number {
  let h = 1779033703 ^ s.length
  for (let i = 0; i < s.length; i++) {
    h = Math.imul(h ^ s.charCodeAt(i), 3432918353)
    h = (h << 13) | (h >>> 19)
  }
  return (h ^= h >>> 16) >>> 0
}
function mulberry32(a: number): () => number {
  return () => {
    a |= 0; a = (a + 0x6D2B79F5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

export function selectCandidates(candidates: Candidate[], opts: SelectionOptions): Candidate[] {
  const { level, density, wordCount, known, learning } = opts
  const target = Math.max(0, Math.round((wordCount / 100) * density))
  if (target === 0) return []
  const rand = mulberry32(hashSeed(opts.seed))

  const eligible = candidates.filter((c) => c.translation && c.level <= level && c.end > c.start)
  if (eligible.length === 0) return []

  // Score: prefer candidates near the chosen level (so raising the level
  // actually changes what you see), prefer learning lemmas, avoid known ones,
  // add jitter for variety. Longer kinds get a mild boost at high levels.
  const scored = eligible.map((c) => {
    let s = 1 - Math.abs(c.level - level) * 0.25
    s += KIND_ORDER[c.kind] * 0.05 * (level - 1) / 4
    const tl = c.targetLemmas ?? []
    if (learning && tl.some((l) => learning.has(l))) s += 0.6
    if (known && tl.length > 0 && tl.every((l) => known.has(l))) s -= 0.8
    s += rand() * 0.5
    return { c, s }
  }).sort((a, b) => b.s - a.s)

  const chosen: Candidate[] = []
  const sentencesUsed = new Set<string>()
  const lemmaCount = new Map<string, number>()
  const overlaps = (c: Candidate) => chosen.some((o) => c.start < o.end && o.start < c.end)

  // Repetition helps retention: once a lemma is chosen, give its other
  // occurrences a second chance in a later pass.
  for (let pass = 0; pass < 2 && chosen.length < target; pass++) {
    for (const { c } of scored) {
      if (chosen.length >= target) break
      if (chosen.includes(c) || overlaps(c)) continue
      const sentKey = c.sentence ? `${c.sentence.start}-${c.sentence.end}` : `${c.start}`
      // At low levels keep at most one swap per sentence so pages stay readable.
      if (level <= 2 && sentencesUsed.has(sentKey)) continue
      const lemma = c.lemmas[0]
      if (pass === 0 && lemma && (lemmaCount.get(lemma) ?? 0) >= 3) continue
      chosen.push(c)
      sentencesUsed.add(sentKey)
      if (lemma) lemmaCount.set(lemma, (lemmaCount.get(lemma) ?? 0) + 1)
    }
  }
  return chosen.sort((a, b) => a.start - b.start)
}
