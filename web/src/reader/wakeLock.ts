// Keep the screen on while reading, via the Screen Wake Lock API.
// The lock needs a secure context (https or localhost) and is released by the
// browser whenever the page is hidden, so it is re-requested on return.
import { useEffect } from 'react'

export function wakeLockSupported(): boolean {
  return typeof navigator !== 'undefined' && 'wakeLock' in navigator && window.isSecureContext
}

export function useWakeLock(enabled: boolean): void {
  useEffect(() => {
    if (!enabled || !wakeLockSupported()) return
    let sentinel: WakeLockSentinel | null = null
    let active = true

    const acquire = async () => {
      if (!active || document.visibilityState !== 'visible' || sentinel) return
      try {
        sentinel = await navigator.wakeLock.request('screen')
        sentinel.addEventListener('release', () => { sentinel = null })
      } catch (err) {
        // Low battery or a browser policy can refuse; nothing to do but try again later.
        console.info('Innesto: wake lock not granted', (err as Error).message)
      }
    }
    const onVisibility = () => { if (document.visibilityState === 'visible') void acquire() }

    void acquire()
    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      active = false
      document.removeEventListener('visibilitychange', onVisibility)
      void sentinel?.release()
      sentinel = null
    }
  }, [enabled])
}
