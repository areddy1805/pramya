// Visual QA: screenshot every major screen (empty state + seeded data).
// Run: pnpm exec tsx scripts/visual-qa.ts  (or node --experimental-strip-types)
import { chromium } from 'playwright'

const BASE = 'http://127.0.0.1:3000'
const OUT = 'scripts/shots'

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
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 })
  const fs = await import('node:fs')
  fs.mkdirSync(OUT, { recursive: true })
  for (const [name, path] of routes) {
    await page.goto(`${BASE}${path}`, { waitUntil: 'networkidle' })
    await page.waitForTimeout(1200)
    await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true })
    console.log(`shot ${name}`)
  }
  await browser.close()
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
