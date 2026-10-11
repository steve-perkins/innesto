import { useEffect } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import Library from './pages/Library'
import Reader from './pages/Reader'
import Settings from './pages/Settings'
import { effectiveTheme, useSettings } from './store/settings'

export default function App() {
  const theme = useSettings((s) => s.theme)
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
        <Route path="/" element={<Library />} />
        <Route path="/read/:id" element={<Reader />} />
        <Route path="/settings" element={<Settings />} />
      </Routes>
    </BrowserRouter>
  )
}
