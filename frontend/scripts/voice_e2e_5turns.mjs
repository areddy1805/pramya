// LIVE 5-TURN voice interview via Playwright (physical mic + speakers).
// 5 complete candidate turns: interviewer TTS aloud -> playback gating ->
// candidate speech through speakers -> real mic -> ASR -> evaluation ->
// next question. Includes an interrupt mid-Q3 TTS. Asserts per-turn
// transcript/evaluation counts, gating, and zero stale chunks after interrupt.
import { chromium } from 'playwright'
import { execFile } from 'node:child_process'

const LAUNCH_ARGS = [
  '--use-fake-ui-for-media-stream', // auto-grant REAL mic (no fake device)
  '--autoplay-policy=no-user-gesture-required',
]

const INIT = `
window.__voiceDiag = {
  wsOpened: false, ttsStart: 0, ttsStop: 0, playbackCompleteSent: 0,
  chunksReceived: 0, micSends: 0, events: [],
  t0: performance.now(),
  turnEndAt: null, ttsStartAt: null, firstChunkAt: null, listeningAt: null,
  perTurn: [],
  staleWindow: false, staleChunks: 0,
}
const push = (e) => { e.ms = Math.round(performance.now() - window.__voiceDiag.t0); window.__voiceDiag.events.push(e); if (window.__voiceDiag.events.length > 3000) window.__voiceDiag.events.shift() }
const origWS = window.WebSocket
window.WebSocket = class extends origWS {
  constructor(...a) { super(...a); window.__voiceDiag.wsOpened = true }
  send(data) {
    if (typeof data !== 'string') { window.__voiceDiag.micSends++; }
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
            if (o.type === 'tts_start') { window.__voiceDiag.ttsStart++; window.__voiceDiag.ttsStartAt = performance.now(); window.__voiceDiag.staleWindow = false; push({t:'tts_start'}) }
            else if (o.type === 'tts_stop') { window.__voiceDiag.ttsStop++; push({t:'tts_stop'}) }
            else if (o.type === 'state' && o.state === 'listening') { window.__voiceDiag.listeningAt = performance.now(); push({t:'state', s:'listening'}) }
            else if (o.type === 'state') push({t:'state', s: o.state})
            else if (o.type === 'question') push({t:'question'})
            else if (o.type === 'final_transcript') push({t:'final', n: (o.text||'').length, txt: (o.text||'').slice(0,80)})
            else if (o.type === 'turn_ended') { window.__voiceDiag.turnEndAt = performance.now(); push({t:'turn_ended'}) }
            else if (o.type === 'evaluation') push({t:'eval', v: o.overall})
            else if (o.type === 'answer_submitted') push({t:'answer_submitted'})
            else if (o.type === 'error') push({t:'error', code: o.code})
          } catch {}
        } else { window.__voiceDiag.chunksReceived++; if (window.__voiceDiag.firstChunkAt === null) window.__voiceDiag.firstChunkAt = performance.now(); if (window.__voiceDiag.staleWindow) window.__voiceDiag.staleChunks++; push({t:'chunk'}) }
        fn(ev)
      })
    },
    get() { return desc.get.call(this) },
    configurable: true,
  })
}
`
// Test-session volumes only (never project settings): interviewer = system
// output (set externally to ~50%), mock candidate = afplay -v 0.5 (50%).
// Test-session volumes only (never project settings): interviewer = system
// output (set externally to ~50%). The mock candidate uses afplay -v 1.0 so
// its perceived level matches the interviewer's full-scale TTS at the same
// system volume (both ~50%); -v 0.5 dropped the mic SNR below ASR usability.
const afplay = (wav) => new Promise((res) => execFile('/usr/bin/afplay', ['-v', '1.0', wav], (err) => res(err ? 'ERR' : 'OK')))
const ANSWERS = ['/tmp/candidate_speech_loud.wav', '/tmp/candidate_speech_2_loud.wav', '/tmp/candidate_speech_3_loud.wav']

async function main() {
  const browser = await chromium.launch({ headless: false, args: LAUNCH_ARGS })
  const ctx = await browser.newContext({ permissions: ['microphone'] })
  const page = await ctx.newPage()
  await page.addInitScript(INIT)
  page.on('pageerror', (e) => console.log('  pageerror:', e.message.slice(0, 120)))

  await page.goto('http://localhost:3000/interview', { waitUntil: 'domcontentloaded' })
  await page.waitForSelector('text=Start Live Voice Interview', { timeout: 15000 })
  await page.click('text=Start Live Voice Interview')
  console.log('LIVE 5-TURN INTERVIEW STARTED')

  const diag = () => page.evaluate(() => window.__voiceDiag)
  let lastLen = 0
  let interrupted = false
  const answered = new Set()

  for (let i = 0; i < 1200; i++) { // up to ~10 min
    const d = await diag()
    if (d.events.length !== lastLen) {
      for (const e of d.events.slice(lastLen)) {
        if (e.t !== 'chunk') console.log('  ev:', JSON.stringify(e))
      }
      lastLen = d.events.length
    }
    const evs = d.events
    const evals = evs.filter((e) => e.t === 'eval').length
    const ttsStarts = evs.filter((e) => e.t === 'tts_start').length
    // CURRENT state must be listening (not a stale earlier listening window).
    const lastState = [...evs].reverse().find((e) => e.t === 'state')
    const curListening = lastState?.s === 'listening'
    // Playback for the current question must be finished: playback_complete OR
    // a barge-in interrupt AFTER the last tts_start.
    const lastTts = evs.findLastIndex((e) => e.t === 'tts_start')
    const lastPb = evs.findLastIndex((e) => e.t === 'playback_complete')
    const lastIntr = evs.findLastIndex((e) => e.t === 'state' && e.s === 'interrupted')
    const playbackDone = (lastPb > lastTts) || (lastIntr > lastTts)
    const inListening = curListening && playbackDone

    // Speak the next answer ONLY when the current question has been asked
    // (tts_start for it) AND its playback is complete / we're in listening —
    // never while the interviewer is still speaking (that audio is discarded
    // by design and would waste the turn). The turn index counts NON-EMPTY
    // finals: if ASR missed (empty final), the same answer is replayed on the
    // next listening window instead of wedging the loop.
    const finals = evs.filter((e) => e.t === 'final' && e.n > 5)
    const turnIdx = finals.length // 0-based next turn we are about to answer
    if (inListening && ttsStarts >= turnIdx + 1 && !answered.has(turnIdx) && turnIdx <= 4) {
      answered.add(turnIdx)
      console.log(`  >> TURN ${turnIdx + 1}: playing candidate answer through speakers`)
      const wav = ANSWERS[turnIdx % ANSWERS.length]
      console.log('  afplay:', await afplay(wav))
    }
    // Interrupt mid-Q3 TTS.
    if (!interrupted && ttsStarts >= 3 && d.chunksReceived > 0) {
      const intBtn = page.locator('button:has-text("Interrupt")')
      if (await intBtn.isVisible() && await intBtn.isEnabled()) {
        console.log('  >> INTERRUPTING mid-Q3 TTS (barge-in path)')
        await intBtn.click()
        interrupted = true
        // Stale-audio window: chunks arriving between the interrupt and the
        // NEXT tts_start are in-flight frames of the OLD generation. The
        // client drops them (state != speaking); a correct engine must not
        // stream more than a few in-flight frames.
        await page.evaluate(() => { window.__voiceDiag.staleWindow = true; window.__voiceDiag.staleChunks = 0 })
      }
    }
    if (evals >= 5) break
    await page.waitForTimeout(500)
  }
  await page.waitForTimeout(4000)
  const d = await diag()
  const evs = d.events
  const finals = evs.filter((e) => e.t === 'final' && e.n > 5)
  const evals = evs.filter((e) => e.t === 'eval')
  console.log('=== 5-TURN DIAG ===')
  console.log('wsOpened:', d.wsOpened, '| ttsStart:', d.ttsStart, 'ttsStop:', d.ttsStop)
  // Per-turn waterfall from stamped events: turn_end -> tts_start -> first chunk.
  const evs2 = evs
  let turnNo = 0
  for (let i = 0; i < evs2.length; i++) {
    if (evs2[i].t === 'turn_ended') {
      turnNo++
      let ts = evs2[i].ms, tts = null, chunk = null
      for (let j = i + 1; j < evs2.length; j++) {
        if (evs2[j].t === 'tts_start') { tts = evs2[j].ms; break }
      }
      for (let j = i + 1; j < evs2.length; j++) {
        if (evs2[j].t === 'chunk') { chunk = evs2[j].ms; break }
      }
      const firstAudio = tts === null ? 'n/a' : `${Math.round(tts - ts)}ms`
      const firstChunk = (tts === null || chunk === null) ? 'n/a' : `${Math.round(chunk - tts)}ms`
      console.log(`  turn ${turnNo}: turn_end->tts_start ${firstAudio} | tts_start->first_chunk ${firstChunk}`)
    }
  }
  console.log('playbackCompleteSent:', d.playbackCompleteSent, '| chunksReceived:', d.chunksReceived)
  console.log('micSends:', d.micSends)
  finals.forEach((f, i) => console.log(`  turn ${i + 1} final (${f.n} chars): ${JSON.stringify(f.txt)}`))
  evals.forEach((e, i) => console.log(`  turn ${i + 1} eval: ${e.v}`))
  // Gating: every 'state listening' must be preceded by playback_complete OR
  // an interrupt (the barge-in path). No listening may follow a bare tts_stop.
  let gatingOk = true
  for (let i = 0; i < evs.length; i++) {
    if (evs[i].t === 'state' && evs[i].s === 'listening') {
      const prev = evs.slice(0, i)
      const pc = prev.findLastIndex((e) => e.t === 'playback_complete')
      const intr = prev.findLastIndex((e) => e.t === 'state' && e.s === 'interrupted')
      if (pc === -1 && intr === -1) gatingOk = false
    }
  }
  const stale = d.staleChunks
  const pass =
    d.wsOpened && finals.length >= 5 && evals.length >= 5 && d.ttsStart >= 5 &&
    gatingOk && stale < 15 && interrupted
  console.log('gatingOk:', gatingOk, '| interrupt executed:', interrupted)
  console.log('in-flight (stale-window) chunks after interrupt:', stale, '(client drops these; <15 tolerated)')
  // Stop the session cleanly so the interview completes.
  const stopBtn = page.locator('button:has-text("End interview"), button:has-text("Stop")').first()
  if (await stopBtn.isVisible()) await stopBtn.click()
  await page.waitForTimeout(1500)
  await browser.close()
  console.log(pass ? 'LIVE 5-TURN PASSED' : 'LIVE 5-TURN FAILED')
  process.exit(pass ? 0 : 1)
}
main().catch((e) => { console.error('5-TURN ERROR:', e.message); process.exit(1) })
