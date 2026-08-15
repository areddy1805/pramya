import { test, expect } from '@playwright/test'

/**
 * Pramya profile-workspace E2E (real frontend + backend + DB).
 *
 * Proves the persistence chain through the actual UI:
 *   create profiles (AI Engineer + FDE) -> upload resume to each ->
 *   upload JD -> duplicate JD (idempotent) -> switch profile ->
 *   isolation -> refresh -> state survives.
 *
 * The frontend addresses the dev user (DEFAULT_USER_ID=1, no auth system),
 * so this test drives user 1's real workspace. It is rerun-tolerant:
 * pre-existing profiles are reused, duplicate uploads dedup (200), and the
 * test never deletes user 1's data (dev workspace is preserved).
 *
 * Backend must be running (make dev-backend); frontend on :3000.
 */

const BASE = process.env.PRAMYA_E2E_BASE ?? 'http://localhost:3000'
const USER_ID = 1

function mdFile(name: string, body: string): { name: string; mimeType: string; buffer: Buffer } {
  return { name, mimeType: 'text/markdown', buffer: Buffer.from(body) }
}

async function ensureProfile(
  request: import('@playwright/test').APIRequestContext,
  name: string,
  positioning: string,
): Promise<number> {
  const list = await request.get(`${BASE}/api/v1/candidates/${USER_ID}/profiles`)
  const existing = (await list.json()) as { name: string; id: number }[]
  const found = existing.find((p) => p.name === name)
  if (found) return found.id
  const res = await request.post(`${BASE}/api/v1/candidates/${USER_ID}/profiles`, {
    data: { name, positioning },
  })
  expect(res.status()).toBe(201)
  return ((await res.json()) as { id: number }).id
}

/** Switch workspace via the header profile switcher (selects by name). */
async function switchTo(page: import('@playwright/test').Page, name: string) {
  await page.locator('header button[title^="Active profile"]').click()
  await page.getByRole('option', { name }).click()
  await expect(page.getByRole('heading', { name })).toBeVisible({ timeout: 15000 })
}

test('profile workspace: create, upload, dedup, switch, isolate, persist', async ({
  page,
  request,
}) => {
  // 1. Ensure both profiles exist (created via API so reruns are stable).
  const aiId = await ensureProfile(request, 'AI Engineer', 'Applied AI / ML systems')
  const fdeId = await ensureProfile(request, 'Forward Deployed Engineer', 'Customer-facing AI adoption')
  expect(aiId).not.toBe(fdeId)

  // 2. Open the profile workspace in the UI.
  await page.goto(`${BASE}/profile`)
  await expect(page.getByRole('heading', { name: 'Career profiles' })).toBeVisible()

  // 3. Switch to AI Engineer and upload its resume.
  await switchTo(page, 'AI Engineer')
  await page.setInputFiles('input[type="file"][accept*=".md"]', mdFile('alex.md', '# Alex\nAI Engineer, 5 years applied ML.'))
  await expect(page.getByText('alex.md').first()).toBeVisible({ timeout: 30000 })

  // 4. Switch to FDE and upload its resume; AI Engineer's resume must not leak.
  await switchTo(page, 'Forward Deployed Engineer')
  await page.setInputFiles('input[type="file"][accept*=".md"]', mdFile('dana.md', '# Dana\nForward deployed engineer, adoption focus.'))
  await expect(page.getByText('dana.md').first()).toBeVisible({ timeout: 30000 })
  await expect(page.getByText('alex.md')).toHaveCount(0)

  // 5. Back to AI Engineer; its resume is still there.
  await switchTo(page, 'AI Engineer')
  await expect(page.getByText('alex.md').first()).toBeVisible({ timeout: 15000 })

  // 6. Upload a JD under AI Engineer.
  await page.setInputFiles('input[type="file"][accept*=".md"]', mdFile('jd-ai.md', '# Applied AI Engineer\nBuild LLM products end to end with evals.'))
  await expect(page.getByText('jd-ai.md').first()).toBeVisible({ timeout: 30000 })

  // 7. Refresh: state must be reconstructed from the server.
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Career profiles' })).toBeVisible()
  await expect(page.getByText('AI Engineer').first()).toBeVisible({ timeout: 15000 })
  await expect(page.getByText('alex.md').first()).toBeVisible({ timeout: 15000 })

  // 8. Server-side persistence: both profiles + profile-scoped docs exist.
  const profiles = await request.get(`${BASE}/api/v1/candidates/${USER_ID}/profiles`)
  expect(profiles.ok()).toBeTruthy()
  const profileList = (await profiles.json()) as { name: string; id: number }[]
  expect(profileList.map((p) => p.name)).toEqual(
    expect.arrayContaining(['AI Engineer', 'Forward Deployed Engineer']),
  )
  const docs = await request.get(
    `${BASE}/api/v1/documents?user_id=${USER_ID}&profile_id=${aiId}`,
  )
  expect(docs.ok()).toBeTruthy()
  const docList = (await docs.json()) as { kind: string; filename: string }[]
  expect(docList.map((d) => d.filename)).toEqual(
    expect.arrayContaining(['alex.md', 'jd-ai.md']),
  )

  // 9. Duplicate JD upload is idempotent (200 deduplicated, no error).
  const jdRes = await request.post(`${BASE}/api/v1/documents`, {
    multipart: {
      user_id: String(USER_ID),
      profile_id: String(aiId),
      kind: 'jd',
      file: mdFile('jd-ai-copy.md', '# Applied AI Engineer\nBuild LLM products end to end with evals.'),
    },
  })
  expect(jdRes.status()).toBe(200)
  const jdBody = (await jdRes.json()) as { status: string; created: boolean; document_id: number }
  expect(jdBody.status).toBe('deduplicated')
  expect(jdBody.created).toBe(false)

  // 10. Isolation: FDE profile has its own resume, not AI Engineer's docs.
  const fdeDocs = await request.get(
    `${BASE}/api/v1/documents?user_id=${USER_ID}&profile_id=${fdeId}`,
  )
  const fdeList = (await fdeDocs.json()) as { filename: string }[]
  expect(fdeList.map((d) => d.filename)).toEqual(expect.arrayContaining(['dana.md']))
  expect(fdeList.map((d) => d.filename)).not.toEqual(
    expect.arrayContaining(['alex.md', 'jd-ai.md']),
  )
})
