import { useCallback, useEffect, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { api, type VocabEntry } from '../api/client'
import { useSettings } from '../store/settings'
import { useVocab } from '../store/vocab'

export default function Vocabulary() {
  const lang = useSettings((s) => s.targetLang)
  const vocab = useVocab()
  const [rows, setRows] = useState<VocabEntry[] | null>(null)
  const [filter, setFilter] = useState<'all' | 'learning' | 'known'>('all')
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()
  const from = (useLocation().state as { from?: string } | null)?.from

  const refresh = useCallback(async () => {
    try { setRows(await api.listVocab(lang)); setError(null) }
    catch (e) { setError((e as Error).message) }
  }, [lang])
  useEffect(() => { void refresh() }, [refresh])

  async function setStatus(e: VocabEntry, status: 'known' | 'learning') {
    await vocab.mark(lang, [e.lemma], status)
    await refresh()
  }
  async function remove(e: VocabEntry) {
    await vocab.unmark(lang, e.lemma)
    await refresh()
  }

  const shown = (rows ?? []).filter((r) => filter === 'all' || r.status === filter)
  const counts = { learning: rows?.filter((r) => r.status === 'learning').length ?? 0,
                   known: rows?.filter((r) => r.status === 'known').length ?? 0 }

  return (
    <>
      <header className="topbar">
        <Link to="/" className="brand">Innesto</Link>
        <h1 className="muted" style={{ fontWeight: 400 }}>Vocabulary · {lang.toUpperCase()}</h1>
        <a href={api.vocabCsvUrl(lang)} download><button>Export CSV</button></a>
        <button onClick={() => navigate(from ?? '/')}>‹ Back</button>
      </header>
      <main className="page">
        {error && <p className="error">{error}</p>}
        <p className="muted">
          {counts.learning} learning · {counts.known} known. Words you tap while reading are added as
          “learning”; mark them known when they no longer need a gloss. Known words are swapped less,
          learning words more.
        </p>
        <div className="filters">
          {(['all', 'learning', 'known'] as const).map((f) => (
            <button key={f} className={filter === f ? 'primary' : undefined} onClick={() => setFilter(f)}>
              {f[0].toUpperCase() + f.slice(1)}
            </button>
          ))}
        </div>
        {rows && shown.length === 0 && <p className="empty">Nothing here yet.</p>}
        {shown.length > 0 && (
          <table className="vocab">
            <thead><tr><th>Word</th><th>Status</th><th>Lookups</th><th>Last seen</th><th></th></tr></thead>
            <tbody>
              {shown.map((e) => (
                <tr key={e.id}>
                  <td lang={lang}>{e.lemma}</td>
                  <td><span className={`badge ${e.status === 'known' ? 'ok' : ''}`}>{e.status}</span></td>
                  <td>{e.lookups}</td>
                  <td className="muted">{new Date(e.last_seen).toLocaleDateString()}</td>
                  <td className="row-actions">
                    {e.status === 'learning'
                      ? <button onClick={() => void setStatus(e, 'known')}>Mark known</button>
                      : <button onClick={() => void setStatus(e, 'learning')}>Back to learning</button>}
                    <button className="danger" onClick={() => void remove(e)}>Remove</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </main>
    </>
  )
}
