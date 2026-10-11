import { useEffect, type ReactNode } from 'react'
import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import Library from './pages/Library'
import Login from './pages/Login'
import Reader from './pages/Reader'
import Settings from './pages/Settings'
import Vocabulary from './pages/Vocabulary'
import { useAuth } from './store/auth'
import { effectiveTheme, useSettings } from './store/settings'

function RequireAuth({ children }: { children: ReactNode }) {
  const token = useAuth((a) => a.accessToken)
  const location = useLocation()
  if (!token) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  return <>{children}</>
}

export default function App() {
  const theme = useSettings((s) => s.theme)
  const refreshUser = useAuth((a) => a.refreshUser)
  useEffect(() => { void refreshUser() }, [refreshUser])
  useEffect(() => {
    const apply = () => { document.documentElement.dataset.theme = effectiveTheme(theme) }
    apply()
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    mq.addEventListener('change', apply)
    return () => mq.removeEventListener('change', apply)
  }, [theme])

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<RequireAuth><Library /></RequireAuth>} />
        <Route path="/read/:id" element={<RequireAuth><Reader /></RequireAuth>} />
        <Route path="/settings" element={<RequireAuth><Settings /></RequireAuth>} />
        <Route path="/vocabulary" element={<RequireAuth><Vocabulary /></RequireAuth>} />
      </Routes>
    </BrowserRouter>
  )
}
