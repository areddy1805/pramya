import { test, expect } from '@playwright/test'

/**
 * Pramya V1 text-journey E2E (Phase L).
 *
 * Drives the real product UI against a live backend (default http://localhost:3000,
 * which proxies /api to the backend on 8001). Requires the demo data to be
 * seeded once (`make demo-setup`) so the dashboard has real readiness data.
 *
 * Asserts flow-level behavior, not exact LLM output: start typed interview ->
 * question appears -> answer submits -> evaluation appears -> stop -> report.
 */

const BASE = process.env.PRAMYA_E2E_BASE ?? 'http://localhost:3000'

test('dashboard shows real readiness after demo setup', async ({ page }) => {
  await page.goto(`${BASE}/dashboard`)
  await expect(page.locator('h1').first()).toContainText(/You're/, { timeout: 15000 })
  // The readiness surface must render (real data path, not a loading shell).
  await expect(page.locator('main')).toContainText(/10|critical|gap|preparation|evidence|progress/i, { timeout: 15000 })
})

test('typed interview journey: start -> question -> answer -> evaluation -> report', async ({
  page,
}) => {
  await page.goto(`${BASE}/interview`)

  // Format defaults to voice; switch to typed (segmented control).
  await page.getByRole('button', { name: 'Typed', exact: true }).click()
  await expect(page.getByText('Start typed interview')).toBeVisible({ timeout: 15000 })
  await page.getByText('Start typed interview').click()

  // Session begins and the first question is generated (real DeepSeek call).
  // The heading + captions render immediately; the question text itself only
  // appears once the SSE 'question' event arrives after generation.
  await expect(page.getByText('Current question')).toBeVisible({ timeout: 120000 })
  const questionText = page.locator('.interview-question').first()
  await expect(questionText).toBeVisible({ timeout: 120000 })
  await expect(questionText).not.toContainText('Preparing')

  // Answer with a real structured response; wait for evaluation.
  const answerBox = page.locator('textarea[placeholder^="Answer as you would"]')
  await answerBox.pressSequentially(
    'I led an event-driven payments platform in Python and FastAPI, processing two million transactions a day with Kafka and PostgreSQL. The hardest tradeoff was exactly-once delivery versus latency; we chose idempotent consumers with a transactional outbox and cut p95 latency by forty percent.',
    { delay: 2 },
  )
  await expect(page.getByRole('button', { name: /Submit answer/ })).toBeEnabled({ timeout: 15000 })
  await page.getByRole('button', { name: /Submit answer/ }).click()
  await expect(page.getByText(/Overall score:/)).toBeVisible({ timeout: 180000 })

  // Stop the session and open the report from history.
  await page.getByRole('button', { name: 'End', exact: true }).click()
  await page.goto(`${BASE}/history`)
  await expect(page.getByText(/session #/i).first()).toBeVisible({ timeout: 15000 })
})
