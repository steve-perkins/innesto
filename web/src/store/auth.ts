// Sign-in state. The access token is a 7-day bearer JWT from /api/auth/google;
// it lives in localStorage (persisted store) and is attached by api/client.ts.
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export interface AuthUser {
  id: string
  email: string | null
  displayName: string | null
  pictureUrl: string | null
  targetLang: string
}

interface AuthStore {
  accessToken: string | null
  user: AuthUser | null
  signIn: (idToken: string) => Promise<void>
  signOut: () => void
  refreshUser: () => Promise<void>
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
  if (!res.ok) {
    let detail = res.statusText
    try { detail = (await res.json()).detail ?? detail } catch { /* not json */ }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

export const useAuth = create<AuthStore>()(
  persist(
    (set, get) => ({
      accessToken: null,
      user: null,

      async signIn(idToken) {
        const r = await post<{ accessToken: string; user: AuthUser }>('/api/auth/google', { idToken })
        set({ accessToken: r.accessToken, user: r.user })
      },

      signOut() {
        set({ accessToken: null, user: null })
      },

      async refreshUser() {
        const token = get().accessToken
        if (!token) return
        const res = await fetch('/api/auth/me', { headers: { Authorization: `Bearer ${token}` } })
        if (res.status === 401 || res.status === 403) { set({ accessToken: null, user: null }); return }
        if (res.ok) set({ user: (await res.json()) as AuthUser })
      },
    }),
    { name: 'innesto.auth' },
  ),
)

/** fetch() with the bearer token; a 401 signs the user out so the router shows /login. */
export async function authFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const token = useAuth.getState().accessToken
  const headers = new Headers(init.headers)
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const res = await fetch(input, { ...init, headers })
  if (res.status === 401) useAuth.getState().signOut()
  return res
}
