import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'
import { VitePWA } from 'vite-plugin-pwa'

// Dev-only CSP: 'unsafe-inline' is required by React Fast Refresh. The
// production CSP (no inline, no blob: scripts) is set by the API server.
const devCsp = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline' blob:",
  "img-src 'self' blob: data:",
  "font-src 'self' blob: data:",
  "connect-src 'self' ws: blob: data:",
  "frame-src 'self' blob:",
  "worker-src 'self' blob:",
  "media-src 'self' blob:",
].join('; ')

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.svg', 'icon.svg'],
      manifest: {
        name: 'Innesto',
        short_name: 'Innesto',
        description: 'A diglot-weave ebook reader for language learners.',
        theme_color: '#2f5d3a',
        background_color: '#f6f1e7',
        display: 'standalone',
        start_url: '/',
        icons: [
          { src: 'icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: 'icon-512.png', sizes: '512x512', type: 'image/png' },
          { src: 'icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
      workbox: {
        // App shell only. Book files and sidecars are cached explicitly in IndexedDB;
        // fonts are cached on first use (per unicode-range subset) rather than precached.
        globPatterns: ['**/*.{js,css,html,svg,png}'],
        globIgnores: ['**/fonts/**'],
        navigateFallbackDenylist: [/^\/api\//],
        runtimeCaching: [{
          urlPattern: /\/fonts\/.*\.(?:woff2|css)$/,
          handler: 'CacheFirst',
          options: { cacheName: 'innesto-fonts', expiration: { maxEntries: 40, maxAgeSeconds: 60 * 60 * 24 * 365 } },
        }],
        maximumFileSizeToCacheInBytes: 4 * 1024 * 1024,
      },
    }),
  ],
  server: {
    strictPort: true,          // fail loudly instead of moving to 5174 (the API proxy and README assume 5173)
    headers: { 'Content-Security-Policy': devCsp },
    proxy: { '/api': 'http://localhost:8000' },
  },
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.ts'],
  },
})
