import { chromium } from 'playwright'
const BASE = 'http://localhost:3000'
const OUT = '../assets/screenshots'
async function main() {
  const browser = await chromium.launch()
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 })
  // Voice-mode interview workspace (flagship CTA visible)
  await page.goto(`${BASE}/interview`)
  await page.waitForTimeout(2500)
  await page.screenshot({ path: `${OUT}/voice.png`, fullPage: true })
  // Report for a completed session with an evaluation
  await page.goto(`${BASE}/interview/68/report`)
  await page.waitForTimeout(9000)
  await page.screenshot({ path: `${OUT}/report.png`, fullPage: true })
  console.log('shot voice + report')
  await browser.close()
}
main().catch((e) => { console.error(e); process.exit(1) })
