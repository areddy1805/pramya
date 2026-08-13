// P0 reproduction: click Cancel mid-interviewer-TTS; measure whether audio
// keeps flowing (chunks received / sources started) after the click.
import { chromium } from 'playwright'

const INIT = `
window.__d = { wsOpened:false, chunks:0, sources:0, state:'idle', events:[] }
const _s = AudioBufferSourceNode.prototype.start
AudioBufferSourceNode.prototype.start = function (...a) { window.__d.sources++; return _s.apply(this, a) }
const origWS = window.WebSocket
window.WebSocket = class extends origWS {
  constructor(...a) { super(...a); window.__d.wsOpened = true }
}
const d = Object.getOwnPropertyDescriptor(origWS.prototype, 'onmessage')
if (d && d.set) {
  const set = d.set
  Object.defineProperty(origWS.prototype, 'onmessage', {
    set(fn) { set.call(this, (ev) => {
      if (typeof ev.data === 'string') { try { const o = JSON.parse(ev.data); window.__d.events.push(o.type); if (o.type==='state') window.__d.state = o.state } catch {} }
      else window.__d.chunks++
      fn(ev)
    }) },
    get() { return d.get.call(this) }, configurable: true,
  })
}
`

async function main() {
  const browser = await chromium.launch({ headless: false, args: ['--use-fake-ui-for-media-stream', '--autoplay-policy=no-user-gesture-required'] })
  const ctx = await browser.newContext({ permissions: ['microphone'] })
  const page = await ctx.newPage()
  await page.addInitScript(INIT)
  await page.goto('http://localhost:3000/interview', { waitUntil: 'domcontentloaded' })
  await page.waitForSelector('text=Start Live Voice Interview', { timeout: 15000 })
  await page.click('text=Start Live Voice Interview')
  // wait until interviewer is mid-TTS (speaking + chunks flowing)
  for (let i = 0; i < 400; i++) {
    const d = await page.evaluate(() => window.__d)
    if (d.state === 'speaking' && d.chunks > 30) break
    await page.waitForTimeout(250)
  }
  const before = await page.evaluate(() => window.__d)
  console.log('before cancel: state=', before.state, 'chunks=', before.chunks, 'sources=', before.sources)
  // Reproduce the user's exact path: the HTTP/SSE session-cancel while the
  // voice WS is live mid-TTS (not the in-page voice Cancel button).
  const sid = await page.evaluate(() => window.location.href)
  const sess = await page.evaluate(async () => {
    const r = await fetch('/api/v1/interviews?user_id=1')
    const j = await r.json()
    return Array.isArray(j.items) ? j.items[0].id : (Array.isArray(j) ? j[0].id : null)
  })
  console.log('cancelling session via HTTP:', sess)
  await page.evaluate(async (id) => {
    await fetch('/api/v1/interviews/' + id + '/cancel?user_id=1', { method: 'POST' })
  }, sess)
  await page.waitForTimeout(3000)
  const after = await page.evaluate(() => window.__d)
  console.log('after cancel:  state=', after.state, 'chunks=', after.chunks, 'sources=', after.sources)
  console.log('new chunks after cancel:', after.chunks - before.chunks)
  console.log('new sources after cancel:', after.sources - before.sources)
  await browser.close()
  const pass = after.chunks - before.chunks === 0
  console.log(pass ? 'CANCEL-STOP OK (no new audio)' : 'CANCEL-STOP FAILED (audio continued)')
  process.exit(pass ? 0 : 1)
}
main().catch((e) => { console.error('ERR', e.message); process.exit(1) })
