import { defineConfig, devices } from '@playwright/test'

/**
 * Pramya V1 browser E2E (Phase L).
 *
 * Runs against a live frontend (vite dev on :3000 by default, proxying /api
 * to the backend on :8001). Servers are expected to be running
 * (`make dev-backend` + `make dev-frontend`); `reuseExistingServer` prevents
 * a second vite instance. Seed demo data once with `make demo-setup` before
 * the journey suite.
 */
export default defineConfig({
  testDir: 'e2e',
  timeout: 240_000,
  fullyParallel: false,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: process.env.PRAMYA_E2E_BASE ?? 'http://localhost:3000',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: 'pnpm dev --port 3000',
    url: 'http://localhost:3000',
    reuseExistingServer: true,
    timeout: 60_000,
  },
})
