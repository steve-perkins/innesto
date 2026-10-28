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

export interface SpeakResult {
  ok: boolean
  /** Human-readable reason when `ok` is false (or a warning when it is true). */
  note?: string
  /** Voice actually used, if any. */
  voice?: string
}

const LANG_NAMES: Record<string, string> = { it: 'Italian', es: 'Spanish', fr: 'French', de: 'German', pt: 'Portuguese', nl: 'Dutch', en: 'English' }

function explainError(code: string, lang: string): string {
  const name = LANG_NAMES[lang] ?? lang.toUpperCase()
  switch (code) {
    case 'language-unavailable':
    case 'voice-unavailable':
      return `The device's speech engine has no ${name} voice. On Android: Settings → Languages & input → Text-to-speech output → engine settings → Install voice data → ${name}.`
    case 'synthesis-unavailable':
    case 'synthesis-failed':
      return 'The device has no working text-to-speech engine (on Android, install "Speech Services by Google").'
    case 'audio-busy':
    case 'audio-hardware':
      return 'The audio device is busy or unavailable; close other apps using sound and try again.'
    case 'not-allowed':
      return 'The browser blocked speech; tap the speaker button again directly.'
    case 'network':
      return 'This voice needs an internet connection; choose a local voice in Settings or reconnect.'
    case 'interrupted':
    case 'canceled':
      return ''
    default:
      return `Speech failed (${code}).`
  }
}

/** Speak `text`; resolves when playback starts, ends or fails, with a diagnosis. */
export async function speak(text: string, lang: string, preferredURI?: string | null): Promise<SpeakResult> {
  if (!ttsAvailable()) return { ok: false, note: 'This browser has no speech synthesis.' }
  if (!text.trim()) return { ok: false, note: 'Nothing to say.' }
  await voicesReady()
  const voice = pickVoice(lang, preferredURI)
  const name = LANG_NAMES[lang] ?? lang.toUpperCase()
  const noVoiceNote = voice ? undefined
    : `No ${name} voice is installed on this device, so the default voice is used. ` + explainError('language-unavailable', lang)

  return new Promise<SpeakResult>((resolve) => {
    const start = () => {
      const u = new SpeechSynthesisUtterance(text)
      u.lang = bcp47(lang)
      if (voice) { u.voice = voice; u.lang = voice.lang }
      u.rate = 0.9
      let settled = false
      const done = (result: SpeakResult) => { if (!settled) { settled = true; resolve(result) } }
      u.onstart = () => done({ ok: true, note: noVoiceNote, voice: voice?.name })
      u.onend = () => { if (current === u) current = null; done({ ok: true, note: noVoiceNote, voice: voice?.name }) }
      u.onerror = (e) => {
        if (current === u) current = null
        const note = explainError(e.error, lang)
        if (note) done({ ok: false, note, voice: voice?.name }); else done({ ok: true, voice: voice?.name })
      }
      current = u
      speechSynthesis.speak(u)
      // Some engines never fire start/end/error when they silently do nothing.
      window.setTimeout(() => done({ ok: false, note: noVoiceNote ?? 'The speech engine did not respond. ' + explainError('synthesis-unavailable', lang), voice: voice?.name }), 4000)
    }
    if (speechSynthesis.speaking || speechSynthesis.pending) {
      speechSynthesis.cancel()
      window.setTimeout(start, 80)      // let the cancel settle before the next speak()
    } else {
      start()
    }
  })
}
