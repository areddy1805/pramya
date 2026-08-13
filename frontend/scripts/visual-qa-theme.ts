// Visual QA: dark (default) + light themes, geometry/overflow/errors, screenshots.
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
  const fs = await import('node:fs')
  fs.mkdirSync('scripts/shots2', { recursive: true })
  let failures = 0

  for (const theme of ['dark', 'light']) {
    for (const [name, path] of routes) {
      const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
      // Set theme preference BEFORE navigation (simulates stored preference).
      await page.addInitScript((t) => {
        localStorage.setItem('pramya-theme', t)
        // Guard: init scripts run before <html> is parsed.
        const root = document.documentElement
        if (root) root.classList.toggle('dark', t === 'dark')
      }, theme)

      const consoleErrors: string[] = []
      const pageErrors: string[] = []
      page.on('console', (msg) => {
        if (msg.type() === 'error') consoleErrors.push(msg.text())
      })
      page.on('pageerror', (err) => pageErrors.push(String(err)))

      await page.goto(`${BASE}${path}`, { waitUntil: 'networkidle' })
      await page.waitForTimeout(700)

      const issues = await page.evaluate((t) => {
        const problems: string[] = []
        const doc = document.documentElement
        if (doc.scrollWidth > doc.clientWidth + 2) {
          problems.push(`HORIZONTAL OVERFLOW: ${doc.scrollWidth} > ${doc.clientWidth}`)
        }
        // Theme applied?
        const darkApplied = doc.classList.contains('dark')
        const bg = getComputedStyle(document.body).backgroundColor
        if ((t === 'dark') !== darkApplied) problems.push(`THEME MISMATCH: wanted ${t}, dark=${darkApplied}`)
        if (bg === 'rgba(0, 0, 0, 0)' || bg === 'transparent') problems.push('TRANSPARENT BODY BG')
        document.querySelectorAll('button, a, input, select, textarea').forEach((el) => {
          const r = el.getBoundingClientRect()
          if (r.width < 4 || r.height < 4) problems.push(`TINY ELEMENT: ${el.tagName}.${String(el.className).slice(0, 40)}`)
        })
        document.querySelectorAll('h1').forEach((el) => {
          if (!el.textContent?.trim()) problems.push('EMPTY H1')
        })
        return problems
      }, theme)

      const all = [...issues, ...consoleErrors.map((e) => `CONSOLE: ${e}`), ...pageErrors.map((e) => `PAGEERROR: ${e}`)]
      // Ignore the known candidates/1 404 (fresh-profile probe).
      const real = all.filter((i) => !i.includes('candidates/1'))
      if (real.length) {
        failures++
        console.log(`\n=== ${theme}/${name} — ${real.length} issue(s)`)
        real.slice(0, 10).forEach((i) => console.log(`  ${i}`))
      } else {
        console.log(`ok ${theme}/${name}`)
      }
      await page.screenshot({ path: `scripts/shots2/${theme}-${name}.png`, fullPage: true })
      await page.close()
    }
  }

  console.log(failures ? `\n${failures} screens with issues` : '\nall screens clean (dark + light)')
  await browser.close()
  process.exit(failures ? 1 : 0)
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
