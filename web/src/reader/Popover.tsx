import { useEffect, useRef } from 'react'
import { useVocab } from '../store/vocab'
import type { Candidate } from './selection'

export interface PopoverProps {
  candidate: Candidate
  /** Anchor rectangle in top-document viewport coordinates. */
  anchor: DOMRect
  targetLang: string
  onClose: () => void
}

export function speak(text: string, lang: string): void {
  if (!('speechSynthesis' in window)) return
  const u = new SpeechSynthesisUtterance(text)
  u.lang = lang === 'it' ? 'it-IT' : lang
  const voice = speechSynthesis.getVoices().find((v) => v.lang.toLowerCase().startsWith(lang.toLowerCase()))
  if (voice) u.voice = voice
  speechSynthesis.cancel()
  speechSynthesis.speak(u)
}

const KIND_LABEL: Record<Candidate['kind'], string> = {
  word: 'word', np: 'noun phrase', vp: 'verb phrase', pp: 'prepositional phrase',
  clause: 'clause', sentence: 'sentence',
}

export default function Popover({ candidate, anchor, targetLang, onClose }: PopoverProps) {
  const ref = useRef<HTMLDivElement>(null)
  const vocab = useVocab()
  const lemmas = candidate.targetLemmas ?? []
  const allKnown = lemmas.length > 0 && lemmas.every((l) => vocab.known.has(l))
  const anyLearning = lemmas.some((l) => vocab.learning.has(l))

  // Position below the swap, flipping above when there is no room.
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const margin = 8
    const w = el.offsetWidth, h = el.offsetHeight
    let left = anchor.left + anchor.width / 2 - w / 2
    left = Math.max(margin, Math.min(window.innerWidth - w - margin, left))
    let top = anchor.bottom + margin
    if (top + h > window.innerHeight - margin) top = anchor.top - h - margin
    el.style.left = `${left}px`
    el.style.top = `${Math.max(margin, top)}px`
  }, [anchor, candidate])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="popover" ref={ref} role="dialog" aria-label="Translation">
      <div className="popover-row">
        <div className="popover-target" lang={targetLang}>{candidate.translation}</div>
        <button className="icon" title="Pronounce" aria-label="Pronounce"
                onClick={() => speak(candidate.translation ?? '', targetLang)}>🔊</button>
      </div>
      <div className="popover-source">{candidate.text}</div>
      <div className="popover-lemmas muted">
        {lemmas.length ? lemmas.join(' · ') : candidate.lemmas.join(' · ')}
        <span className="popover-kind"> · {KIND_LABEL[candidate.kind]} · level {candidate.level}</span>
      </div>
      {lemmas.length > 0 && (
        <div className="popover-actions">
          <button className={anyLearning && !allKnown ? 'primary' : undefined}
                  onClick={() => void vocab.mark(targetLang, lemmas, 'learning')}>Learning</button>
          <button className={allKnown ? 'primary' : undefined}
                  onClick={() => void vocab.mark(targetLang, lemmas, 'known')}>I know this</button>
        </div>
      )}
    </div>
  )
}
