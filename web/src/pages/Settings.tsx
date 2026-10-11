import { Link } from 'react-router-dom'
import { defaultSettings, useSettings, type Flow, type Theme } from '../store/settings'

const LEVELS = ['', 'A1 · common words', 'A2 · simple phrases', 'B1 · verb phrases', 'B2 · clauses', 'C1 · whole sentences']

export default function Settings() {
  const s = useSettings()
  return (
    <>
      <header className="topbar">
        <Link to="/" className="brand">Innesto</Link>
        <h1 className="muted" style={{ fontWeight: 400 }}>Settings</h1>
        <Link to="/"><button>Library</button></Link>
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
            <select id="targetLang" value={s.targetLang} onChange={(e) => s.set({ targetLang: e.target.value })}>
              <option value="it">Italian</option>
            </select>
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
            (MIT) and the Helsinki-NLP Opus-MT models (CC BY 4.0).
          </p>
          <button onClick={() => s.set(defaultSettings)}>Reset settings</button>
        </section>
      </main>
    </>
  )
}
