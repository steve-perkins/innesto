// Where pronunciation voices come from, per platform. The app only asks the
// browser to speak; the voices themselves are installed at the OS or browser
// level, and a missing language is silent on some engines (notably Android).

type Platform = 'android' | 'ios' | 'windows' | 'mac' | 'linux' | 'other'

export function detectPlatform(): Platform {
  const ua = navigator.userAgent
  if (/Android/i.test(ua)) return 'android'
  if (/iPhone|iPad|iPod/i.test(ua) || (/Macintosh/.test(ua) && navigator.maxTouchPoints > 1)) return 'ios'
  if (/Windows/i.test(ua)) return 'windows'
  if (/Macintosh|Mac OS X/i.test(ua)) return 'mac'
  if (/Linux|X11/i.test(ua)) return 'linux'
  return 'other'
}

const GUIDES: { id: Platform; title: string; steps: string[] }[] = [
  {
    id: 'android',
    title: 'Android (Chrome, or the installed app)',
    steps: [
      'Voices come from the system text-to-speech engine, not from Chrome. Without the language installed, playback is often silent with no error.',
      'Settings → General management → Language → Text-to-speech output (Samsung One UI), or Settings → System → Languages & input → Text-to-speech output (other Android devices).',
      'Preferred engine: "Speech Services by Google" (install it from the Play Store if it is missing; the Samsung engine also works).',
      'Tap the engine\'s settings (gear) → Install voice data → choose the language → download a voice.',
      'Use the Play button on that screen to confirm it speaks, then come back here and press "Play sample".',
    ],
  },
  {
    id: 'ios',
    title: 'iPhone and iPad (Safari, Chrome, or the installed app)',
    steps: [
      'All browsers on iOS use Apple\'s voices.',
      'Settings → Accessibility → Spoken Content → Voices → choose the language → download a voice (for example Alice for Italian, Mónica for Spanish). Enhanced voices sound better.',
      'The voice list here updates after reopening the app.',
    ],
  },
  {
    id: 'windows',
    title: 'Windows (Chrome, Edge)',
    steps: [
      'Edge offers high-quality online "Natural" voices for most languages with nothing to install; Chrome offers Google online voices. Both need an internet connection.',
      'For offline voices: Settings → Time & language → Language & region → Add a language → tick "Text-to-speech" during the install.',
      'New voices appear after restarting the browser.',
    ],
  },
  {
    id: 'mac',
    title: 'macOS (Chrome, Edge, Safari)',
    steps: [
      'Browsers use the macOS voices, plus Google (Chrome) or Microsoft Natural (Edge) online voices when connected.',
      'System Settings → Accessibility → Spoken Content → System Voice → Manage Voices… → download voices for the language (Alice, Mónica…). Premium and Enhanced variants sound best.',
      'Restart the browser to see newly downloaded voices.',
    ],
  },
  {
    id: 'linux',
    title: 'Linux',
    steps: [
      'Chrome and Edge provide online voices; offline voices depend on speech-dispatcher and an installed engine such as espeak-ng or Piper, which the browser picks up on restart.',
    ],
  },
]

export default function VoiceHelp({ lang }: { lang: string }) {
  const here = detectPlatform()
  const ordered = [...GUIDES].sort((a, b) => (a.id === here ? -1 : b.id === here ? 1 : 0))
  return (
    <details className="voice-help">
      <summary>Where do voices come from? (no sound, wrong language, or no {lang.toUpperCase()} voice listed)</summary>
      <p className="muted">
        Innesto only asks your browser to speak. The voices themselves belong to the device or browser, so a
        language has to be installed there once. Online voices (Google, Microsoft Natural) need a connection;
        downloaded voices work offline. After installing, reopen the app or restart the browser.
      </p>
      {ordered.map((g) => (
        <div key={g.id} className={`voice-guide${g.id === here ? ' current' : ''}`}>
          <h3>{g.title}{g.id === here ? ' · this device' : ''}</h3>
          <ol>{g.steps.map((s, i) => <li key={i}>{s}</li>)}</ol>
        </div>
      ))}
    </details>
  )
}
