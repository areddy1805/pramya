// Voice client for live spoken mock interviews (Phase 9).
//
// Protocol (see backend/app/voice/engine.py):
//   client -> server: JSON control (start_turn, end_turn, interrupt, pause,
//                     resume, stop, cancel) + binary PCM16 16 kHz mic frames
//   server -> client: JSON events (state, question, tts_start/stop,
//                     partial_transcript, final_transcript, evaluation, error)
//                     + binary PCM16 24 kHz playback chunks
//
// Interruption is a correctness requirement: interrupt clears the playback
// queue AND tells the server to cancel in-flight TTS; stale audio never
// plays after an interrupt.

export type VoiceState =
  | 'idle'
  | 'listening'
  | 'processing'
  | 'speaking'
  | 'paused'
  | 'interrupted'
  | 'cancelled'
  | 'completed'
  | 'error'

export interface VoiceEvent {
  type: string
  state?: VoiceState
  text?: string
  question_id?: number
  difficulty?: string
  overall?: number | null
  code?: string
  message?: string
}

export interface VoiceQuestion {
  id: number
  text: string
  difficulty: string
}

export interface VoiceTranscriptLine {
  role: 'interviewer' | 'candidate'
  text: string
  partial?: boolean
}

export interface VoiceHandlers {
  onState?: (state: VoiceState) => void
  onQuestion?: (q: VoiceQuestion) => void
  onPartial?: (text: string) => void
  onFinalTranscript?: (text: string) => void
  onEvaluation?: (overall: number | null, answerId?: number) => void
  onError?: (code: string, message: string) => void
  onTTSStart?: () => void
  onTTSStop?: () => void
  onClosed?: () => void
}

const TARGET_SAMPLE_RATE = 16000
const PLAYBACK_SAMPLE_RATE = 24000

export class VoiceClient {
  private ws: WebSocket | null = null
  private stream: MediaStream | null = null
  private audioCtx: AudioContext | null = null
  private captureNode: AudioWorkletNode | null = null
  private playbackQueue: AudioBuffer[] = []
  private playing = false
  private closedByUser = false
  public state: VoiceState = 'idle'
  private url: string
  private handlers: VoiceHandlers

  constructor(
    url: string,
    handlers: VoiceHandlers = {},
  ) {
    this.url = url
    this.handlers = handlers
  }

  // -- lifecycle ------------------------------------------------------------

  async start(): Promise<void> {
    this.closedByUser = false
    this.playbackQueue = []
    // Playback context first (user gesture unlocks audio).
    this.audioCtx = new AudioContext({ latencyHint: 'interactive' })
    if (this.audioCtx.state === 'suspended') await this.audioCtx.resume()

    // Capture: mic -> AudioWorklet -> PCM16 16 kHz -> WS binary frames.
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        channelCount: 1,
        sampleRate: TARGET_SAMPLE_RATE,
      },
    })
    await this.audioCtx.audioWorklet.addModule(
      URL.createObjectURL(
        new Blob([CAPTURE_WORKLET_SOURCE], { type: 'application/javascript' }),
      ),
    )
    const source = this.audioCtx.createMediaStreamSource(this.stream)
    this.captureNode = new AudioWorkletNode(this.audioCtx, 'pcm16-capture', {
      numberOfInputs: 1,
      numberOfOutputs: 0,
    })
    this.captureNode.port.onmessage = (ev: MessageEvent) => {
      if (this.ws?.readyState === WebSocket.OPEN && this.state === 'listening') {
        this.ws.send(ev.data as ArrayBuffer)
      }
    }
    source.connect(this.captureNode)

    this.ws = new WebSocket(this.url)
    this.ws.binaryType = 'arraybuffer'
    this.ws.onmessage = (ev) => this.handleMessage(ev)
    this.ws.onclose = () => {
      this.state = 'idle'
      this.handlers.onClosed?.()
      if (!this.closedByUser) this.handlers.onError?.('ws_closed', 'Voice connection lost')
    }
  }

  async stop(): Promise<void> {
    this.closedByUser = true
    this.sendControl('stop')
    await this.teardown()
    this.state = 'completed'
    this.handlers.onState?.('completed')
  }

  async cancel(): Promise<void> {
    this.closedByUser = true
    this.sendControl('cancel')
    await this.teardown()
    this.state = 'cancelled'
    this.handlers.onState?.('cancelled')
  }

  private async teardown(): Promise<void> {
    this.captureNode?.disconnect()
    this.captureNode = null
    this.stream?.getTracks().forEach((t) => t.stop())
    this.stream = null
    if (this.ws && this.ws.readyState <= WebSocket.OPEN) this.ws.close()
    this.ws = null
    // Flush playback buffer + close context (no stale audio).
    this.playbackQueue = []
    if (this.audioCtx) {
      await this.audioCtx.close()
      this.audioCtx = null
    }
  }

  // -- controls -------------------------------------------------------------

  sendControl(type: string): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type }))
    }
  }

  /** Barge-in: clear local playback NOW and tell the server to cancel TTS. */
  interrupt(): void {
    this.playbackQueue = []
    this.playing = false
    this.sendControl('interrupt')
  }

  pause(): void {
    this.sendControl('pause')
  }

  resume(): void {
    this.sendControl('resume')
  }

  // -- messaging ------------------------------------------------------------

  private handleMessage(ev: MessageEvent): void {
    if (typeof ev.data === 'string') {
      let payload: VoiceEvent
      try {
        payload = JSON.parse(ev.data)
      } catch {
        return
      }
      this.dispatch(payload)
    } else {
      // Binary PCM16 24 kHz playback chunk.
      this.enqueuePlayback(ev.data as ArrayBuffer)
    }
  }

  private dispatch(payload: VoiceEvent): void {
    switch (payload.type) {
      case 'state':
        this.state = payload.state ?? 'idle'
        if (payload.state === 'interrupted') {
          // Server confirmed interruption: flush local playback.
          this.playbackQueue = []
          this.playing = false
        }
        this.handlers.onState?.(this.state)
        break
      case 'question':
        this.handlers.onQuestion?.({
          id: payload.question_id ?? 0,
          text: payload.text ?? '',
          difficulty: payload.difficulty ?? 'medium',
        })
        break
      case 'partial_transcript':
        this.handlers.onPartial?.(payload.text ?? '')
        break
      case 'final_transcript':
        this.handlers.onFinalTranscript?.(payload.text ?? '')
        break
      case 'evaluation':
        this.handlers.onEvaluation?.(payload.overall ?? null)
        break
      case 'tts_start':
        this.handlers.onTTSStart?.()
        break
      case 'tts_stop':
        this.handlers.onTTSStop?.()
        break
      case 'error':
        this.handlers.onError?.(payload.code ?? 'error', payload.message ?? 'Voice error')
        break
    }
  }

  // -- playback -------------------------------------------------------------

  private enqueuePlayback(data: ArrayBuffer): void {
    if (!this.audioCtx) return
    const pcm = new Int16Array(data)
    const buffer = this.audioCtx.createBuffer(1, pcm.length, PLAYBACK_SAMPLE_RATE)
    const channel = buffer.getChannelData(0)
    for (let i = 0; i < pcm.length; i++) channel[i] = pcm[i] / 32768
    this.playbackQueue.push(buffer)
    void this.drainPlayback()
  }

  private async drainPlayback(): Promise<void> {
    if (this.playing || !this.audioCtx || this.playbackQueue.length === 0) return
    this.playing = true
    try {
      while (this.playbackQueue.length > 0) {
        if (this.state === 'interrupted' || this.state === 'cancelled') break
        const buf = this.playbackQueue.shift()
        if (!buf) break
        await new Promise<void>((resolve) => {
          const src = this.audioCtx!.createBufferSource()
          src.buffer = buf
          src.connect(this.audioCtx!.destination)
          src.onended = () => resolve()
          src.start()
        })
      }
    } finally {
      this.playing = false
    }
  }
}

// AudioWorklet module: downsample to 16 kHz mono PCM16 and emit buffers.
const CAPTURE_WORKLET_SOURCE = `
class Pcm16Capture extends AudioWorkletProcessor {
  constructor() {
    super()
    this.acc = new Float32Array(0)
  }
  process(inputs) {
    const input = inputs[0]
    if (!input || input.length === 0 || !input[0] || input[0].length === 0) return true
    const chan = input[0]
    const merged = new Float32Array(this.acc.length + chan.length)
    merged.set(this.acc)
    merged.set(chan, this.acc.length)
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
registerProcessor('pcm16-capture', Pcm16Capture)
`
