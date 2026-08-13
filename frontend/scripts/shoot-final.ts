// Final UI screenshots for README/docs: dark (flagship) + light key screens.
// Output: assets/screenshots/ (repo root) — committed for documentation use.
import { chromium } from 'playwright'

const BASE = 'http://127.0.0.1:3000'
const OUT = '../assets/screenshots'

const darkRoutes = [
  ['dashboard', '/dashboard'],
  ['setup', '/setup'],
  ['preparation', '/preparation'],
  ['interview', '/interview'],
  ['evidence', '/evidence'],
  ['progress', '/progress'],
  ['stories', '/stories'],
  ['settings', '/settings'],
  ['runtime', '/models'],
]

const lightRoutes = [['light-dashboard', '/dashboard'], ['light-interview', '/interview'], ['light-evidence', '/evidence']]

async function main() {
  const browser = await chromium.launch()
  const fs = await import('node:fs')
  fs.mkdirSync(OUT, { recursive: true })

  for (const [theme, routes] of [
    ['dark', darkRoutes],
    ['light', lightRoutes],
  ] as const) {
    for (const [name, path] of routes) {
      const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 })
      await page.addInitScript((t) => {
        localStorage.setItem('pramya-theme', t)
        const root = document.documentElement
        if (root) root.classList.toggle('dark', t === 'dark')
      }, theme)
      await page.goto(`${BASE}${path}`, { waitUntil: 'networkidle' })
      await page.waitForTimeout(1400)
      const filename = name.startsWith('light-') ? `${name}.png` : `${name}.png`
      await page.screenshot({ path: `${OUT}/${filename}`, fullPage: true })
      console.log(`shot ${filename}`)
      await page.close()
    }
  }
  await browser.close()
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
