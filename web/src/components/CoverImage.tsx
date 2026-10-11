// <img> cannot send an Authorization header, so covers are fetched with the
// token and shown through an object URL (kept per book id for the session).
import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { authFetch } from '../store/auth'

const urls = new Map<string, Promise<string | null>>()

function coverObjectUrl(bookId: string): Promise<string | null> {
  let p = urls.get(bookId)
  if (!p) {
    p = authFetch(api.coverUrl(bookId))
      .then(async (r) => (r.ok ? URL.createObjectURL(await r.blob()) : null))
      .catch(() => null)
    urls.set(bookId, p)
  }
  return p
}

export default function CoverImage({ bookId, title }: { bookId: string; title: string }) {
  const [src, setSrc] = useState<string | null>(null)
  useEffect(() => {
    let live = true
    void coverObjectUrl(bookId).then((u) => { if (live) setSrc(u) })
    return () => { live = false }
  }, [bookId])
  return src ? <img src={src} alt="" /> : <div className="placeholder">{title}</div>
}
