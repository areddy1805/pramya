// ONE controlled real-model Live Voice E2E (H.1-H.9 validation).
// Fake mic = real TTS speech (silence-padded) so speech lands in LISTENING.
// Instruments: WS connect, tts_start/chunks/tts_stop, AudioContext state,
// AudioBufferSourceNode starts, getUserMedia track state, mic PCM sends.
import { chromium } from 'playwright'

const LAUNCH_ARGS = [
  '--use-fake-device-for-media-stream',
  '--use-fake-ui-for-media-stream',
  '--autoplay-policy=no-user-gesture-required',
  '--use-file-for-fake-audio-capture=/tmp/mic_input.wav',
]

const INIT = `
window.__voiceDiag = {
  wsOpened: false, wsClosed: false,
  ttsStart: 0, ttsStop: 0, chunksReceived: 0, chunkBytes: 0,
  audioCtxState: [], ctxResumeCalls: 0,
  bufferSourcesStarted: 0,
  micTrackState: null, getUserMediaCalls: 0,
  micSends: 0, micBytes: 0,
  events: [],
  errors: [],
}
const push = (e) => { window.__voiceDiag.events.push(e); if (window.__voiceDiag.events.length > 500) window.__voiceDiag.events.shift() }
const origWS = window.WebSocket
window.WebSocket = class extends origWS {
  constructor(...a) { super(...a); window.__voiceDiag.wsOpened = true; this.__bin = 0 }
  send(data) {
    if (typeof data !== 'string') { window.__voiceDiag.micSends++; window.__voiceDiag.micBytes += data.byteLength || 0 }
    return super.send(data)
  }
}
// Wire receive-side counters: patch onmessage on the real prototype.
const origProto = origWS.prototype
const desc = Object.getOwnPropertyDescriptor(origProto, 'onmessage')
if (desc && desc.set) {
  const origSet = desc.set
  Object.defineProperty(origProto, 'onmessage', {
    set(fn) {
      origSet.call(this, (ev) => {
        if (typeof ev.data === 'string') {
          try {
            const o = JSON.parse(ev.data)
            if (o.type === 'tts_start') { window.__voiceDiag.ttsStart++; push({t:'tts_start', g: o.generation}) }
            else if (o.type === 'tts_stop') { window.__voiceDiag.ttsStop++; push({t:'tts_stop', g: o.generation}) }
            else if (o.type === 'state') { push({t:'state', s: o.state}) }
            else if (o.type === 'question') { push({t:'question'}) }
            else if (o.type === 'partial_transcript') { push({t:'partial', n: (o.text||'').length}) }
            else if (o.type === 'final_transcript') { push({t:'final', n: (o.text||'').length}) }
            else if (o.type === 'evaluation') { push({t:'eval', v: o.overall}) }
            else if (o.type === 'turn_ended') { push({t:'turn_ended'}) }
            else if (o.type === 'answer_submitted') { push({t:'answer_submitted'}) }
            else if (o.type === 'error') { push({t:'error', code: o.code}) }
          } catch {}
        } else {
          window.__voiceDiag.chunksReceived++
          window.__voiceDiag.chunkBytes += ev.data.byteLength || 0
          push({t:'chunk', b: ev.data.byteLength || 0})
        }
        fn(ev)
      })
    },
    get() { return desc.get.call(this) },
    configurable: true,
  })
}
const origGetUM = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices)
navigator.mediaDevices.getUserMedia = async (c) => {
  window.__voiceDiag.getUserMediaCalls++
  const s = await origGetUM(c)
  const t = s.getAudioTracks()[0]
  window.__voiceDiag.micTrackState = t ? t.readyState : 'none'
  return s
}
const origAC = window.AudioContext
window.AudioContext = class extends origAC {
  constructor(...a) { super(...a); push({t:'ctx_created', state: this.state}); window.__voiceDiag.audioCtxState.push(this.state) }
  resume() { window.__voiceDiag.ctxResumeCalls++; const r = super.resume(); r.then(() => { window.__voiceDiag.audioCtxState.push(this.state); push({t:'ctx_state', state: this.state}) }); return r }
}
const origStart = AudioBufferSourceNode.prototype.start
AudioBufferSourceNode.prototype.start = function(...a) {
  window.__voiceDiag.bufferSourcesStarted++
  push({t:'buffer_start'})
  return origStart.apply(this, a)
}
`

async function main() {
  const browser = await chromium.launch({ args: LAUNCH_ARGS })
  const ctx = await browser.newContext({ permissions: ['microphone'] })
  const page = await ctx.newPage()
  await page.addInitScript(INIT)
  const consoleErrors = []
  page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text().slice(0, 200)) })
  page.on('pageerror', (e) => consoleErrors.push('PAGEERROR: ' + e.message.slice(0, 200)))

  await page.goto('http://localhost:3000/interview', { waitUntil: 'domcontentloaded' })
  await page.waitForSelector('text=Start Live Voice Interview', { timeout: 15000 })
  await page.click('text=Start Live Voice Interview')
  console.log('clicked Start Live Voice Interview')

  // Phase 1: interviewer question TTS stream (speech starts ~10-12s in)
  const diag = () => page.evaluate(() => window.__voiceDiag)
  let prev = null
  for (let i = 0; i < 240; i++) { // up to 120s
    const d = await diag()
    if (prev === null || d.events.length !== prev.events.length) {
      const newEvents = prev === null ? d.events : d.events.slice(prev.events.length)
      for (const e of newEvents) console.log('  ev:', JSON.stringify(e))
      prev = d
    }
    if (d.ttsStart >= 2 && d.chunksReceived > 0 && d.bufferSourcesStarted > 0) {
      // second question TTS started -> interrupt mid-stream
      const intBtn = page.locator('button:has-text("Interrupt")')
      if (await intBtn.isVisible() && await intBtn.isEnabled()) {
        console.log('INTERRUPTING mid-second-question-TTS')
        await intBtn.click()
        break
      }
    }
    await page.waitForTimeout(500)
  }
  const d = await diag()
  console.log('=== DIAG ===')
  console.log('wsOpened:', d.wsOpened, 'wsClosed:', d.wsClosed)
  console.log('ttsStart:', d.ttsStart, 'ttsStop:', d.ttsStop)
  console.log('chunksReceived:', d.chunksReceived, 'bytes:', d.chunkBytes)
  console.log('audioCtxState:', d.audioCtxState, 'resumeCalls:', d.ctxResumeCalls)
  console.log('bufferSourcesStarted:', d.bufferSourcesStarted)
  console.log('getUserMediaCalls:', d.getUserMediaCalls, 'micTrackState:', d.micTrackState)
  console.log('micSends:', d.micSends, 'micBytes:', d.micBytes)
  console.log('consoleErrors:', consoleErrors.slice(0, 8))

  await page.waitForTimeout(8000) // let interrupt settle into listening + ASR
  const d2 = await diag()
  console.log('=== POST-INTERRUPT ===')
  console.log('chunksReceived (must NOT grow):', d2.chunksReceived, '(was', d.chunksReceived + ')')
  console.log('ttsStop count:', d2.ttsStop)
  console.log('micSends after:', d2.micSends)

  await browser.close()
  const pass =
    d.wsOpened &&
    d.ttsStart >= 1 &&
    d.chunksReceived > 0 &&
    d.audioCtxState.includes('running') &&
    d.bufferSourcesStarted > 0 &&
    d.getUserMediaCalls >= 1 &&
    d.micTrackState === 'live' &&
    d.micSends > 0 &&
    d2.chunksReceived === d.chunksReceived // no stale chunks after interrupt
  console.log(pass ? 'E2E DIAGNOSTIC PASSED' : 'E2E DIAGNOSTIC FAILED')
  process.exit(pass ? 0 : 1)
}
main().catch((e) => { console.error(e); process.exit(1) })
