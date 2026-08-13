// MIC PROBE: does the physical mic capture room speech at all, and does
// Parakeet transcribe it? Captures raw PCM16 16kHz (echoCancellation OFF,
// noiseSuppression OFF) while candidate speech plays through the speakers.
import { chromium } from 'playwright'
import { execFile } from 'node:child_process'
import { writeFileSync } from 'node:fs'

const afplay = (wav) => new Promise((res) => execFile('/usr/bin/afplay', [wav], () => res('OK')))

const PAGE = `
<button id="go">capture 9s</button><pre id="log"></pre>
<script>
const log = (m) => { document.getElementById('log').textContent += m + '\\n' }
let pcmChunks = []
document.getElementById('go').onclick = async () => {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false, channelCount: 1 } })
  const ctx = new AudioContext({ sampleRate: 48000 })
  await ctx.audioWorklet.addModule(URL.createObjectURL(new Blob([WORKLET], { type: 'application/javascript' })))
  const src = ctx.createMediaStreamSource(stream)
  const node = new AudioWorkletNode(ctx, 'probe')
  node.port.onmessage = (e) => { pcmChunks.push(e.data) }
  src.connect(node)
  log('capturing...')
  setTimeout(async () => {
    const total = pcmChunks.reduce((n, c) => n + c.byteLength, 0)
    const buf = new Uint8Array(total)
    let off = 0
    for (const c of pcmChunks) { buf.set(new Uint8Array(c), off); off += c.byteLength }
    window.__pcm = Array.from(buf)
    log('captured bytes: ' + total)
  }, 9000)
}
const WORKLET = \`
class Probe extends AudioWorkletProcessor {
  constructor() {
    super()
    this.acc = new Float32Array(0)
  }
  process(inputs) {
    const input = inputs[0]
    if (!input || !input[0] || !input[0].length) return true
    const chan = input[0]
    const merged = new Float32Array(this.acc.length + chan.length)
    merged.set(this.acc); merged.set(chan, this.acc.length)
    this.acc = merged
    const step = sampleRate / 16000
    const outLen = Math.floor(this.acc.length / step)
    if (outLen < 1) return true
    const out = new Int16Array(outLen)
    for (let i = 0; i < outLen; i++) {
      const v = this.acc[Math.floor(i * step)]
      out[i] = Math.max(-1, Math.min(1, v)) * 32767
    }
    this.acc = this.acc.slice(Math.floor(outLen * step))
    this.port.postMessage(out.buffer)
    return true
  }
}
registerProcessor('probe', Probe)
\`
</script>`

async function main() {
  const browser = await chromium.launch({ headless: false, args: ['--use-fake-ui-for-media-stream', '--autoplay-policy=no-user-gesture-required'] })
  const ctx = await browser.newContext({ permissions: ['microphone'] })
  const page = await ctx.newPage()
  await page.route('**/probe', (route) => route.fulfill({ contentType: 'text/html', body: PAGE }))
  await page.goto('http://localhost:3000/probe', { waitUntil: 'domcontentloaded' })
  page.on('console', (m) => console.log('  page.console:', m.text().slice(0, 200)))
  page.on('pageerror', (e) => console.log('  pageerror:', e.message.slice(0, 200)))
  await page.click('#go')
  await page.waitForTimeout(600)
  console.log('playing candidate speech through speakers...')
  console.log('afplay:', await afplay('/tmp/candidate_speech_loud.wav'))
  await page.waitForFunction(() => document.getElementById('log').textContent.includes('captured bytes'), null, { timeout: 30000 })
  const pcm = await page.evaluate(() => window.__pcm)
  console.log('captured PCM bytes:', pcm.length)
  writeFileSync('/tmp/mic_probe.pcm', Buffer.from(pcm))
  // wrap WAV + post to oMLX
  const fs = await import('node:fs')
  const hdr = Buffer.alloc(44)
  const dataLen = pcm.length
  hdr.write('RIFF', 0); hdr.writeUInt32LE(36 + dataLen, 4); hdr.write('WAVE', 8)
  hdr.write('fmt ', 12); hdr.writeUInt32LE(16, 16); hdr.writeUInt16LE(1, 20); hdr.writeUInt16LE(1, 22)
  hdr.writeUInt32LE(16000, 24); hdr.writeUInt32LE(32000, 28); hdr.writeUInt16LE(2, 32); hdr.writeUInt16LE(16, 34)
  hdr.write('data', 36); hdr.writeUInt32LE(dataLen, 40)
  fs.writeFileSync('/tmp/mic_probe.wav', Buffer.concat([hdr, Buffer.from(pcm)]))
  const { execFileSync } = await import('node:child_process')
  const curl = execFileSync('curl', [
    '-s', '-X', 'POST', 'http://127.0.0.1:8000/v1/audio/transcriptions',
    '-F', 'model=parakeet-tdt-0.6b-v3-int8',
    '-F', 'response_format=json',
    '-F', 'file=@/tmp/mic_probe.wav',
  ], { encoding: 'utf8' })
  const j = JSON.parse(curl)
  console.log('ASR text:', JSON.stringify(j.text), 'chars:', (j.text || '').length)
  await browser.close()
}
main().catch((e) => { console.error('PROBE ERROR:', e.message); process.exit(1) })
