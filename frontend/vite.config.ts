import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true,
        // AI endpoints routinely take 20-120s (local inference): never let
        // the dev proxy cut them off with its default 30s timeout.
        timeout: 180_000,
        proxyTimeout: 180_000,
      },
    },
  },
})
