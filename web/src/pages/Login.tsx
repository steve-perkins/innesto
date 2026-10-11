import { GoogleLogin, GoogleOAuthProvider } from '@react-oauth/google'
import { useEffect, useState } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { api } from '../api/client'
import { useAuth } from '../store/auth'

export default function Login() {
  const { accessToken, signIn } = useAuth()
  const [clientId, setClientId] = useState<string | null>(null)
  const [configured, setConfigured] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const from = (useLocation().state as { from?: string } | null)?.from ?? '/'

  useEffect(() => {
    api.authConfig()
      .then((c) => { setClientId(c.clientId); setConfigured(c.configured) })
      .catch((e) => setError(`Cannot reach the server: ${(e as Error).message}`))
  }, [])

  if (accessToken) return <Navigate to={from} replace />

  return (
    <main className="login">
      <div className="login-card">
        <div className="brand" style={{ fontSize: '1.6rem' }}>Innesto</div>
        <p className="muted">A diglot-weave reader: your books, with the language you are learning grafted in.</p>
        {!configured && (
          <p className="error">Google sign-in is not configured on this server (INNESTO_GOOGLE_CLIENT_ID).</p>
        )}
        {clientId && configured && (
          <GoogleOAuthProvider clientId={clientId}>
            <GoogleLogin
              onSuccess={(cred) => {
                setError(null)
                if (!cred.credential) { setError('Google returned no credential'); return }
                signIn(cred.credential).catch((e) => {
                  console.error('Innesto sign-in failed:', e)
                  setError(`Sign-in refused by the server: ${(e as Error).message}`)
                })
              }}
              onError={() => setError('Google sign-in failed')}
              useOneTap
              theme="filled_blue" shape="pill" text="signin_with" />
          </GoogleOAuthProvider>
        )}
        {error && <p className="error login-error" role="alert">{error}</p>}
        <p className="muted small">Access is by invitation: only listed Google accounts can sign in.</p>
      </div>
    </main>
  )
}
