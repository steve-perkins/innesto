import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { api, type Language } from '../api/client'
import { speak, ttsAvailable, voicesFor, voicesReady } from '../reader/tts'
import { wakeLockSupported } from '../reader/wakeLock'
import VoiceHelp from '../components/VoiceHelp'
import { useAuth } from '../store/auth'
import { defaultSettings, FONT_LABELS, fontStack, useSettings, type Flow, type FontFamily, type Theme } from '../store/settings'

const LEVELS = ['', 'A1 · common words', 'A2 · simple phrases', 'B1 · verb phrases', 'B2 · clauses', 'C1 · whole sentences']

function VoicePicker({ lang, value, onChange }: { lang: string; value: string | null; onChange: (v: string | null) => void }) {
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([])
  const [note, setNote] = useState<string | null>(null)
  useEffect(() => {
    if (!ttsAvailable()) return
    const update = () => setVoices(voicesFor(lang))
    void voicesReady().then(update)
    speechSynthesis.addEventListener('voiceschanged', update)
    window.addEventListener('online', update)
    window.addEventListener('offline', update)
    return () => {
      speechSynthesis.removeEventListener('voiceschanged', update)
      window.removeEventListener('online', update)
      window.removeEventListener('offline', update)
    }
  }, [lang])
  if (!ttsAvailable()) return <div className="hint">This browser has no speech synthesis.</div>
  return (
    <>
      <div className="field">
        <label htmlFor="voice">Voice</label>
        <select id="voice" value={value ?? ''} onChange={(e) => onChange(e.target.value || null)}>
          <option value="">Automatic{voices[0] ? ` (${voices[0].name})` : ''}</option>
          {voices.map((v) => (
            <option key={v.voiceURI} value={v.voiceURI}>{v.name} · {v.lang}{v.localService ? '' : ' · online'}</option>
          ))}
        </select>
        <div className="hint">
          {voices.length === 0
            ? `No ${lang.toUpperCase()} voice is installed on this device; see "Where do voices come from?" below.`
            : 'Automatic prefers high-quality online voices (Google in Chrome, Microsoft Natural in Edge) and falls back to local voices when offline.'}
        </div>
      </div>
      <div className="field">
        <label>Test</label>
        <button onClick={() => {
          setNote('Speaking…')
          void speak(SAMPLES[lang] ?? 'John is reading a book.', lang, value)
            .then((r) => setNote(r.ok ? `Played with ${r.voice ?? 'the default voice'}.${r.note ? ' ' + r.note : ''}` : r.note ?? 'Speech failed.'))
        }}>🔊 Play sample</button>
        {note && <div className={`hint${note.startsWith('Played') || note === 'Speaking…' ? '' : ' error'}`}>{note}</div>}
      </div>
      <VoiceHelp lang={lang} />
    </>
  )
}

const FALLBACK_LANGUAGES: Language[] = [{ code: 'it', name: 'Italian', available: true }, { code: 'es', name: 'Spanish', available: true }]

const SAMPLES: Record<string, string> = {
  it: 'Buongiorno! John sta leggendo un libro.',
  es: '¡Buenos días! John está leyendo un libro.',
}

export default function Settings() {
  const s = useSettings()
  const [languages, setLanguages] = useState<Language[]>(FALLBACK_LANGUAGES)
  useEffect(() => { api.languages().then(setLanguages).catch(() => undefined) }, [])
  const currentLang = languages.find((l) => l.code === s.targetLang)
  const navigate = useNavigate()
  const from = (useLocation().state as { from?: string } | null)?.from
  const back = () => navigate(from ?? '/')
  const auth = useAuth()
  return (
    <>
      <header className="topbar">
        <Link to="/" className="brand">Innesto</Link>
        <h1 className="muted" style={{ fontWeight: 400 }}>Settings</h1>
        <button onClick={back}>‹ Back{from?.startsWith('/read/') ? ' to book' : ' to library'}</button>
      </header>
      <main className="page settings">
        <section>
          <h2>Reading</h2>
          <div className="field">
            <label htmlFor="theme">Theme</label>
            <select id="theme" value={s.theme} onChange={(e) => s.set({ theme: e.target.value as Theme })}>
              <option value="system">System</option>
              <option value="light">Light</option>
              <option value="sepia">Sepia</option>
              <option value="dark">Dark</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="fontFamily">Font</label>
            <select id="fontFamily" value={s.fontFamily} onChange={(e) => s.set({ fontFamily: e.target.value as FontFamily })}>
              {(Object.keys(FONT_LABELS) as FontFamily[]).map((f) => <option key={f} value={f}>{FONT_LABELS[f]}</option>)}
            </select>
            <div className="hint font-preview" style={{ fontFamily: fontStack(s.fontFamily) ?? 'serif' }}>
              {s.fontFamily === 'book'
                ? 'Uses the fonts the book specifies (or the browser default).'
                : 'John is reading un libro. Maria aprì la porta e entrò in cucina.'}
            </div>
          </div>
          <div className="field">
            <label htmlFor="fontSize">Text size: {s.fontSize}%</label>
            <input id="fontSize" type="range" min={70} max={200} step={5} value={s.fontSize}
                   onChange={(e) => s.set({ fontSize: Number(e.target.value) })} />
          </div>
          <div className="field">
            <label htmlFor="lineHeight">Line height: {s.lineHeight.toFixed(2)}</label>
            <input id="lineHeight" type="range" min={1.1} max={2.2} step={0.05} value={s.lineHeight}
                   onChange={(e) => s.set({ lineHeight: Number(e.target.value) })} />
          </div>
          <div className="field">
            <label htmlFor="keepAwake">Keep screen awake while reading</label>
            <input id="keepAwake" type="checkbox" checked={s.keepAwake}
                   onChange={(e) => s.set({ keepAwake: e.target.checked })} />
            <div className="hint">
              {wakeLockSupported()
                ? 'Stops the screen from dimming or locking while a book is open. Released when you leave the reader or switch apps.'
                : 'Not available in this browser' + (window.isSecureContext ? '.' : ' over plain http; it works on https.')}
            </div>
          </div>
          <div className="field">
            <label htmlFor="flow">Layout</label>
            <select id="flow" value={s.flow} onChange={(e) => s.set({ flow: e.target.value as Flow })}>
              <option value="paginated">Pages</option>
              <option value="scrolled">Scroll</option>
            </select>
          </div>
        </section>

        <section>
          <h2>Language weaving</h2>
          <div className="field">
            <label htmlFor="level">Level: {s.level} — {LEVELS[s.level]}</label>
            <input id="level" type="range" min={1} max={5} step={1} value={s.level}
                   onChange={(e) => s.set({ level: Number(e.target.value) })} />
            <div className="hint">Which words and phrases may be shown in the target language. Higher levels add rarer vocabulary and longer phrases.</div>
          </div>
          <div className="field">
            <label htmlFor="density">Density: {s.density} per 100 words</label>
            <input id="density" type="range" min={1} max={40} step={1} value={s.density}
                   onChange={(e) => s.set({ density: Number(e.target.value) })} />
            <div className="hint">How many swaps appear on a page.</div>
          </div>
          <div className="field">
            <label htmlFor="swapColor">Swap color</label>
            <input id="swapColor" type="color" value={s.swapColor}
                   onChange={(e) => s.set({ swapColor: e.target.value })} />
          </div>
          <div className="field">
            <label htmlFor="targetLang">Target language</label>
            <select id="targetLang" value={s.targetLang} onChange={(e) => s.set({ targetLang: e.target.value, voiceURI: null })}>
              {languages.map((l) => (
                <option key={l.code} value={l.code}>{l.name}{l.available ? '' : ' (model not installed)'}</option>
              ))}
            </select>
            {currentLang && !currentLang.available && (
              <div className="hint">
                No translation model is installed for {currentLang.name}. On the server run
                {' '}<code>python -m scripts.fetch_model en {currentLang.code}</code>, then process your books from the library.
              </div>
            )}
            <div className="hint">Each language has its own translations and vocabulary; switching does not lose anything.</div>
          </div>
          <VoicePicker lang={s.targetLang} value={s.voiceURI} onChange={(v) => s.set({ voiceURI: v })} />
        </section>

        <section>
          <h2>Account</h2>
          <div className="account">
            {auth.user?.pictureUrl && <img className="avatar" src={auth.user.pictureUrl} alt="" referrerPolicy="no-referrer" />}
            <div>
              <div>{auth.user?.displayName ?? 'Signed in'}</div>
              <div className="muted">{auth.user?.email}</div>
            </div>
            <button onClick={() => { auth.signOut(); navigate('/login') }}>Sign out</button>
          </div>
        </section>

        <section>
          <h2>About Innesto</h2>
          <p>
            <em>Innesto</em> is Italian for a <em>graft</em>: a branch from one tree joined to another so
            that they grow together. The app grafts words and phrases from the language you are learning
            into books written in a language you already read.
          </p>
          <p>
            It is based on the <strong>diglot weave</strong> technique: reading a text in your native
            language in which an increasing share of words and phrases has been replaced by the target
            language, so that vocabulary and grammar are absorbed in context. Tap any swapped phrase to see
            the original.
          </p>
          <p className="muted" style={{ fontSize: '0.85rem' }}>
            Built on foliate-js (MIT), spaCy (MIT), wordfreq (Apache-2.0, data CC BY-SA 4.0), CTranslate2
            (MIT) and Opus-MT / Argos translation models (CC BY 4.0). Bundled fonts Noto Serif and Noto Sans
            are under the SIL Open Font License 1.1.
          </p>
          <button onClick={() => s.set(defaultSettings)}>Reset settings</button>
        </section>
      </main>
    </>
  )
}
