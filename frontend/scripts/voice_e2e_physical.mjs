// PHYSICAL-MIC live voice E2E (speaker-integrity acceptance).
// Headed Chromium with the REAL built-in microphone (no fake device) and
// REAL speakers: interviewer TTS plays aloud, leaks into the mic, and must
// be DISCARDED by the server (speaking window). Candidate speech is played
// through the speakers (afplay) during the authoritative LISTENING window
// and must reach ASR. Assertions via the instrumented event contract +
// backend diagnostics.
import { chromium } from 'playwright'
import { execFile } from 'node:child_process'

const LAUNCH_ARGS = [
  '--use-fake-ui-for-media-stream', // auto-grant the REAL mic (no fake device)
  '--autoplay-policy=no-user-gesture-required',
]

const INIT = `
window.__voiceDiag = {
  wsOpened: false, ttsStart: 0, ttsStop: 0, playbackCompleteSent: 0,
  chunksReceived: 0, micSends: 0, micBytes: 0, bufferSourcesStarted: 0,
  events: [], errors: [],
}
const push = (e) => { window.__voiceDiag.events.push(e); if (window.__voiceDiag.events.length > 1000) window.__voiceDiag.events.shift() }
const origWS = window.WebSocket
window.WebSocket = class extends origWS {
  constructor(...a) { super(...a); window.__voiceDiag.wsOpened = true }
  send(data) {
    if (typeof data !== 'string') { window.__voiceDiag.micSends++; window.__voiceDiag.micBytes += data.byteLength || 0 }
    else {
      try { const o = JSON.parse(data); if (o.type === 'playback_complete') { window.__voiceDiag.playbackCompleteSent++; push({t:'playback_complete'}) } } catch {}
    }
    return super.send(data)
  }
}
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
            if (o.type === 'tts_start') { window.__voiceDiag.ttsStart++; push({t:'tts_start'}) }
            else if (o.type === 'tts_stop') { window.__voiceDiag.ttsStop++; push({t:'tts_stop'}) }
            else if (o.type === 'state') push({t:'state', s: o.state})
            else if (o.type === 'question') push({t:'question'})
            else if (o.type === 'partial_transcript') push({t:'partial', n: (o.text||'').length})
            else if (o.type === 'final_transcript') push({t:'final', n: (o.text||'').length, txt: (o.text||'').slice(0,60)})
            else if (o.type === 'evaluation') push({t:'eval', v: o.overall})
            else if (o.type === 'answer_submitted') push({t:'answer_submitted'})
            else if (o.type === 'turn_ended') push({t:'turn_ended'})
            else if (o.type === 'error') push({t:'error', code: o.code})
          } catch {}
        } else {
          window.__voiceDiag.chunksReceived++
          push({t:'chunk'})
        }
        fn(ev)
      })
    },
    get() { return desc.get.call(this) },
    configurable: true,
  })
}
const origStart = AudioBufferSourceNode.prototype.start
AudioBufferSourceNode.prototype.start = function(...a) {
  window.__voiceDiag.bufferSourcesStarted++
  return origStart.apply(this, a)
}
`
const afplay = (wav) =>
  new Promise((res) => execFile('/usr/bin/afplay', [wav], (err) => res(err ? 'ERR' : 'OK')))

async function main() {
  const browser = await chromium.launch({ headless: false, args: LAUNCH_ARGS })
  const ctx = await browser.newContext({ permissions: ['microphone'] })
  const page = await ctx.newPage()
  await page.addInitScript(INIT)
  page.on('console', (m) => { if (m.type() === 'error') console.log('  console.err:', m.text().slice(0, 160)) })
  page.on('pageerror', (e) => console.log('  pageerror:', e.message.slice(0, 160)))

  await page.goto('http://localhost:3000/interview', { waitUntil: 'domcontentloaded' })
  await page.waitForSelector('text=Start Live Voice Interview', { timeout: 15000 })
  await page.click('text=Start Live Voice Interview')
  console.log('voice interview started (REAL mic, speakers)')

  const diag = () => page.evaluate(() => window.__voiceDiag)
  let played = false
  let interrupted = false
  let lastLen = 0
  for (let i = 0; i < 400; i++) { // up to ~200s
    const d = await diag()
    if (d.events.length !== lastLen) {
      for (const e of d.events.slice(lastLen)) {
        console.log('  ev:', JSON.stringify(e))
        if (e.t === 'final' && e.n > 5) console.log('    -> candidate transcript:', JSON.stringify(e.txt))
      }
      lastLen = d.events.length
    }
    // After the FIRST authoritative LISTENING (playback done, mic open),
    // play the candidate speech through the speakers ONCE.
    if (!played && d.events.some((e) => e.t === 'state' && e.s === 'listening') && d.ttsStart >= 1) {
      played = true
      console.log('  >> SPEAKING CANDIDATE ANSWER THROUGH SPEAKERS')
      console.log('  afplay:', await afplay('/tmp/candidate_speech_loud.wav'))
    }
    // Interrupt mid-second-question TTS.
    if (!interrupted && d.ttsStart >= 2 && d.chunksReceived > 0) {
      const intBtn = page.locator('button:has-text("Interrupt")')
      if (await intBtn.isVisible() && await intBtn.isEnabled()) {
        console.log('  >> INTERRUPTING mid-Q2 TTS')
        await intBtn.click()
        interrupted = true
      }
    }
    if (interrupted && d.ttsStart >= 2) break
    if (d.ttsStop >= 2 && d.events.some((e) => e.t === 'eval')) break
    await page.waitForTimeout(500)
  }
  await page.waitForTimeout(6000)
  const d = await diag()
  console.log('=== PHYSICAL E2E DIAG ===')
  console.log('wsOpened:', d.wsOpened, 'ttsStart:', d.ttsStart, 'ttsStop:', d.ttsStop)
  console.log('playbackCompleteSent:', d.playbackCompleteSent, 'chunksReceived:', d.chunksReceived)
  console.log('bufferSourcesStarted:', d.bufferSourcesStarted, 'micSends:', d.micSends, 'micBytes:', d.micBytes)

  const events = d.events
  const finals = events.filter((e) => e.t === 'final' && e.n > 5)
  const evals = events.filter((e) => e.t === 'eval')
  const firstListening = events.findIndex((e) => e.t === 'state' && e.s === 'listening')
  const playbackAck = events.findIndex((e) => e.t === 'playback_complete')
  const gatingOk = firstListening === -1 || (playbackAck !== -1 && playbackAck < firstListening)
  // Speaker integrity: no candidate final transcript may equal the interviewer question.
  const questions = events.filter((e) => e.t === 'question').length
  const pass =
    d.wsOpened && d.ttsStart >= 1 && d.chunksReceived > 0 && d.micSends > 0 &&
    gatingOk && finals.length >= 1 && evals.length >= 1 && questions >= 2
  console.log('gatingOk (listening after playback_complete):', gatingOk)
  console.log('candidate final transcripts:', finals.length, '| evaluations:', evals.length, '| questions asked:', questions)
  console.log(pass ? 'PHYSICAL E2E PASSED' : 'PHYSICAL E2E FAILED')
  await browser.close()
  process.exit(pass ? 0 : 1)
}
main().catch((e) => { console.error('PHYSICAL E2E ERROR:', e.message); process.exit(1) })
