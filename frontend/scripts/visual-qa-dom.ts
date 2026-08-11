// DOM-based visual QA: geometry, overflow, console/page errors, failed
// requests, missing content. Run against the dev server.
import { chromium } from 'playwright'

const BASE = 'http://127.0.0.1:3000'

const routes = [
  ['dashboard', '/dashboard'],
  ['setup', '/setup'],
  ['preparation', '/preparation'],
  ['interview', '/interview'],
  ['progress', '/progress'],
  ['evidence', '/evidence'],
  ['stories', '/stories'],
  ['settings', '/settings'],
  ['runtime', '/models'],
]

async function main() {
  const browser = await chromium.launch()
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  let failures = 0
  for (const [name, path] of routes) {
    const consoleErrors: string[] = []
    const pageErrors: string[] = []
    const failedRequests: string[] = []
    page.on('console', (msg) => {
      if (msg.type() === 'error') consoleErrors.push(msg.text())
    })
    page.on('pageerror', (err) => pageErrors.push(String(err)))
    page.on('requestfailed', (req) => failedRequests.push(`${req.method()} ${req.url()} ${req.failure()?.errorText ?? ''}`))

    await page.goto(`${BASE}${path}`, { waitUntil: 'networkidle' })
    await page.waitForTimeout(800)

    const issues = await page.evaluate(() => {
      const problems: string[] = []
      const doc = document.documentElement
      if (doc.scrollWidth > doc.clientWidth + 2) {
        problems.push(`HORIZONTAL OVERFLOW: scrollWidth ${doc.scrollWidth} > clientWidth ${doc.clientWidth}`)
      }
      // Buttons with zero size or negative
      document.querySelectorAll('button, a, input, select, textarea').forEach((el) => {
        const r = el.getBoundingClientRect()
        if (r.width < 4 || r.height < 4) problems.push(`TINY ELEMENT: ${el.tagName}.${el.className}`)
      })
      // Empty headings
      document.querySelectorAll('h1').forEach((el) => {
        if (!el.textContent?.trim()) problems.push('EMPTY H1')
      })
      // Visible text overflowing its box (approx: check h1/p with scrollWidth > clientWidth)
      document.querySelectorAll('h1, h2, p, span, button').forEach((el) => {
        const r = el.getBoundingClientRect()
        if (r.width > 0 && el.scrollWidth > el.clientWidth + 4) {
          problems.push(`TEXT CLIP: ${el.tagName} "${el.textContent?.slice(0, 40)}"`)
        }
      })
      return problems
    })

    const all = [...issues, ...consoleErrors.map((e) => `CONSOLE: ${e}`), ...pageErrors.map((e) => `PAGEERROR: ${e}`), ...failedRequests.map((e) => `FAILREQ: ${e}`)]
    if (all.length) {
      failures++
      console.log(`\n=== ${name} (${path}) — ${all.length} issue(s)`)
      all.slice(0, 12).forEach((i) => console.log(`  ${i}`))
    } else {
      console.log(`ok ${name}`)
    }
  }
  console.log(failures ? `\n${failures} screens with issues` : '\nall screens clean')
  await browser.close()
  process.exit(failures ? 1 : 0)
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
