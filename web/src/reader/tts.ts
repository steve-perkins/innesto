// Text-to-speech for swapped phrases, with workarounds for browser quirks:
// - voices load asynchronously (getVoices() is empty until `voiceschanged`);
// - Chromium resets the voice to the default when speak() follows cancel()
//   in the same tick, and may drop utterances that get garbage-collected;
// - network ("Google …") voices fail silently when offline, and some
//   browsers only honour `lang` if a matching voice is also set explicitly.

let voices: SpeechSynthesisVoice[] = []
let current: SpeechSynthesisUtterance | null = null   // keep a reference: see GC note

function refresh(): void {
  if (!('speechSynthesis' in window)) return
  voices = speechSynthesis.getVoices()
}
if ('speechSynthesis' in window) {
  refresh()
  speechSynthesis.addEventListener?.('voiceschanged', refresh)
}

export function ttsAvailable(): boolean {
  return 'speechSynthesis' in window && 'SpeechSynthesisUtterance' in window
}

export function bcp47(lang: string): string {
  const map: Record<string, string> = { it: 'it-IT', es: 'es-ES', fr: 'fr-FR', de: 'de-DE', pt: 'pt-PT', nl: 'nl-NL', en: 'en-US' }
  return map[lang] ?? lang
}

/** Voices usable for `lang`, best first: exact region, then local, then the rest. */
export function voicesFor(lang: string): SpeechSynthesisVoice[] {
  if (!voices.length) refresh()
  const base = lang.toLowerCase().split('-')[0]
  const full = bcp47(lang).toLowerCase()
  const norm = (l: string) => l.toLowerCase().replace('_', '-')
  return voices
    .filter((v) => norm(v.lang).split('-')[0] === base)
    .sort((a, b) => score(b) - score(a))
  function score(v: SpeechSynthesisVoice): number {
    return (norm(v.lang) === full ? 4 : 0) + (v.localService ? 2 : 0) + (v.default ? 1 : 0)
  }
}

export function pickVoice(lang: string, preferredURI?: string | null): SpeechSynthesisVoice | undefined {
  const list = voicesFor(lang)
  return (preferredURI && list.find((v) => v.voiceURI === preferredURI)) || list[0]
}

export function speak(text: string, lang: string, preferredURI?: string | null): void {
  if (!ttsAvailable() || !text.trim()) return
  const start = () => {
    const u = new SpeechSynthesisUtterance(text)
    u.lang = bcp47(lang)
    const voice = pickVoice(lang, preferredURI)
    if (voice) { u.voice = voice; u.lang = voice.lang }
    u.rate = 0.9
    u.onend = u.onerror = () => { if (current === u) current = null }
    current = u
    speechSynthesis.speak(u)
  }
  if (speechSynthesis.speaking || speechSynthesis.pending) {
    speechSynthesis.cancel()
    window.setTimeout(start, 60)      // let the cancel settle before the next speak()
  } else {
    start()
  }
}
