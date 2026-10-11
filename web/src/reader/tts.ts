// Text-to-speech for swapped phrases, with workarounds for browser quirks:
// - voices load asynchronously (getVoices() is empty until `voiceschanged`),
//   so the list is re-read on every call rather than cached once;
// - Chromium falls back to the default (English) voice when speak() follows
//   cancel() in the same tick, or when `voice` is unset and only `lang` is
//   given, so a matching voice is always set explicitly;
// - utterances that get garbage-collected mid-speech are dropped in Chromium,
//   so the current one is kept referenced;
// - network voices (Google in Chrome, Microsoft "Online (Natural)" in Edge)
//   sound best but fail silently offline, so they are skipped when offline.

// macOS ships character voices in every language; never pick them automatically.
const NOVELTY = /^(Eddy|Flo|Grandma|Grandpa|Reed|Rocko|Sandy|Shelley|Bad News|Bahh|Bells|Boing|Bubbles|Cellos|Good News|Jester|Organ|Superstar|Trinoids|Whisper|Wobble|Zarvox|Albert|Fred|Junior|Kathy|Ralph)\b/i
// High-quality voices, preferred when online.
const PREMIUM = /Google|Online \(Natural\)|Natural|Neural|Premium|Enhanced/i

let current: SpeechSynthesisUtterance | null = null

export function ttsAvailable(): boolean {
  return typeof window !== 'undefined' && 'speechSynthesis' in window && 'SpeechSynthesisUtterance' in window
}

export function bcp47(lang: string): string {
  const map: Record<string, string> = { it: 'it-IT', es: 'es-ES', fr: 'fr-FR', de: 'de-DE', pt: 'pt-PT', nl: 'nl-NL', en: 'en-US' }
  return map[lang] ?? lang
}

const norm = (l: string) => l.toLowerCase().replace('_', '-')

/** Resolve once voices are loaded (or after a short timeout). */
export function voicesReady(): Promise<SpeechSynthesisVoice[]> {
  if (!ttsAvailable()) return Promise.resolve([])
  const now = speechSynthesis.getVoices()
  if (now.length) return Promise.resolve(now)
  return new Promise((resolve) => {
    const done = () => { speechSynthesis.removeEventListener('voiceschanged', done); resolve(speechSynthesis.getVoices()) }
    speechSynthesis.addEventListener('voiceschanged', done)
    window.setTimeout(done, 1500)
  })
}

export function voiceScore(v: SpeechSynthesisVoice, lang: string): number {
  const online = typeof navigator === 'undefined' ? true : navigator.onLine !== false
  let s = 0
  if (norm(v.lang) === bcp47(lang).toLowerCase()) s += 4
  if (PREMIUM.test(v.name)) s += online ? 8 : -8      // best quality, but useless offline
  if (!v.localService && !online) s -= 16
  if (v.localService) s += 1
  if (v.default) s += 1
  if (NOVELTY.test(v.name)) s -= 32
  return s
}

/** Voices usable for `lang`, best first. */
export function voicesFor(lang: string): SpeechSynthesisVoice[] {
  if (!ttsAvailable()) return []
  const base = lang.toLowerCase().split('-')[0]
  return speechSynthesis.getVoices()
    .filter((v) => norm(v.lang).split('-')[0] === base)
    .sort((a, b) => voiceScore(b, lang) - voiceScore(a, lang))
}

export function pickVoice(lang: string, preferredURI?: string | null): SpeechSynthesisVoice | undefined {
  const list = voicesFor(lang)
  return (preferredURI && list.find((v) => v.voiceURI === preferredURI)) || list[0]
}

export async function speak(text: string, lang: string, preferredURI?: string | null): Promise<void> {
  if (!ttsAvailable() || !text.trim()) return
  await voicesReady()
  const start = () => {
    const u = new SpeechSynthesisUtterance(text)
    u.lang = bcp47(lang)
    const voice = pickVoice(lang, preferredURI)
    if (voice) { u.voice = voice; u.lang = voice.lang }
    else console.warn(`Innesto: no ${lang} voice installed; the browser default will be used`)
    u.rate = 0.9
    u.onend = u.onerror = () => { if (current === u) current = null }
    current = u
    speechSynthesis.speak(u)
  }
  if (speechSynthesis.speaking || speechSynthesis.pending) {
    speechSynthesis.cancel()
    window.setTimeout(start, 80)      // let the cancel settle before the next speak()
  } else {
    start()
  }
}
