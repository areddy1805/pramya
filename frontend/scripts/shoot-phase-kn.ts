// Phase K/N screenshots: History, Debriefs, Transcript (dark flagship).
// Output: assets/screenshots/ — committed for documentation use.
import { chromium } from 'playwright'

const BASE = 'http://localhost:3000'
const OUT = '../assets/screenshots'

const routes: [string, string][] = [
  ['history', '/history'],
  ['debriefs', '/debriefs'],
  ['transcript', '/interview/40/transcript'],
]

async function main() {
  const browser = await chromium.launch()
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 })
  for (const [name, path] of routes) {
    await page.goto(`${BASE}${path}`)
    await page.waitForTimeout(3500) // let data + fonts settle
    await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true })
    console.log(`shot ${name}`)
  }
  await browser.close()
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
