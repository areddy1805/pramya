// Voice client for live spoken mock interviews (Phase 9 / H.5-H.9).
//
// Protocol (see backend/app/voice/engine.py):
//   client -> server: JSON control (start_turn, end_turn, interrupt, pause,
//                     resume, stop, cancel) + binary PCM16 16 kHz mic frames
//   server -> client: JSON events (state, question, tts_start{generation},
//                     tts_stop{generation}, partial_transcript,
//                     final_transcript, evaluation, answer_submitted, error)
//                     + binary PCM16 24 kHz playback chunks
//
// Correctness guarantees:
//  - H.6 playback lifecycle: AudioContext created synchronously inside the
//    user gesture (before any await); playback refuses to run unless the
//    context is 'running'.
//  - H.7 stale-generation protection: every TTS stream has a generation id;
//    chunks are only accepted while state==='speaking' AND the generation
//    matches the current one; interrupt/cancel invalidates the generation so
//    stale audio is dropped, never played.
//  - H.9 permission handling: getUserMedia failures map to actionable
//    error codes (permission_denied / device_unavailable / mic_unavailable).

export type VoiceState =
  | 'idle'
  | 'starting'
  | 'thinking'
  | 'listening'
  | 'processing'
  | 'speaking'
  | 'paused'
  | 'interrupted'
  | 'reconnecting'
  | 'cancelled'
  | 'completed'
  | 'error'

export interface VoiceEvent {
  type: string
  state?: VoiceState
  text?: string
  question?: string
  question_id?: number
  difficulty?: string
  source?: string | null
  source_ref?: string | null
  overall?: number | null
  generation?: number
  answer_id?: number
  code?: string
  message?: string
}

export interface VoiceQuestion {
  id: number
  text: string
  difficulty: string
  source?: string | null
  source_ref?: string | null
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
  onAnswerSubmitted?: (answerId?: number) => void
  onTurnEnded?: () => void
  onError?: (code: string, message: string) => void
  onTTSStart?: (generation?: number) => void
  onTTSStop?: (generation?: number) => void
  onResume?: (q: VoiceQuestion | null) => void
  onReconnecting?: () => void
  onReconnected?: () => void
  onClosed?: () => void
}

const TARGET_SAMPLE_RATE = 16000
const PLAYBACK_SAMPLE_RATE = 24000

export function micErrorMessage(err: unknown): { code: string; message: string } {
  const name = err instanceof DOMException ? err.name : ''
  if (name === 'NotAllowedError' || name === 'PermissionDeniedError') {
    return {
      code: 'permission_denied',
      message: 'Microphone permission was denied. Allow the mic in your browser and try again.',
    }
  }
  if (name === 'NotFoundError' || name === 'DevicesNotFoundError') {
    return {
      code: 'device_unavailable',
      message: 'No microphone was found. Plug one in and try again.',
    }
  }
  if (name === 'NotReadableError') {
    return {
      code: 'mic_unavailable',
      message: 'The microphone is in use by another app. Close it and try again.',
    }
  }
  return {
    code: 'mic_start_failed',
    message: err instanceof Error ? err.message : 'Could not start the microphone.',
  }
}

export class VoiceClient {
  private ws: WebSocket | null = null
  private stream: MediaStream | null = null
  private audioCtx: AudioContext | null = null
  private captureNode: AudioWorkletNode | null = null
  private playbackQueue: AudioBuffer[] = []
  private closedByUser = false
  private heartbeat?: ReturnType<typeof setInterval>
  private reconnectTimer?: ReturnType<typeof setTimeout>
  private reconnectAttempts = 0
  private readonly maxReconnectAttempts = 5
  private readonly reconnectBaseDelayMs = 1000
  public state: VoiceState = 'idle'
  private currentGeneration = -1
  private pendingPlaybackGeneration = -1
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
    this.activeSources.clear()
    this.nextPlaybackAt = 0
    this.currentGeneration = -1
    this.pendingPlaybackGeneration = -1

    // H.6: create + resume AudioContext synchronously inside the user
    // gesture (start() is called directly from the click handler).
    this.audioCtx = new AudioContext({ latencyHint: 'interactive' })
    if (this.audioCtx.state === 'suspended') {
      await this.audioCtx.resume()
    }
    if (this.audioCtx.state !== 'running') {
      throw new Error('Audio output could not start. Unlock audio and try again.')
    }

    // H.9: mic capture with actionable failure mapping.
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          channelCount: 1,
          sampleRate: TARGET_SAMPLE_RATE,
        },
      })
    } catch (err) {
      await this.teardown()
      throw micErrorMessage(err)
    }

    // AudioWorklet capture: mic -> PCM16 16 kHz -> WS binary frames.
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
      // Mic frames flow while the session is in an audio-relevant state:
      // LISTENING (accepted by the server for candidate ASR) or SPEAKING
      // (discarded by the server, counted as diagnostics, and usable for
      // opt-in voice barge-in). The SERVER is authoritative about whether
      // audio becomes a candidate answer — the client never decides that.
      if (this.ws?.readyState === WebSocket.OPEN && (this.state === 'listening' || this.state === 'speaking')) {
        this.ws.send(ev.data as ArrayBuffer)
      }
    }
    source.connect(this.captureNode)

    this.openSocket()
  }

  /**
   * R14: open the WS to the SAME session URL. On a later unexpected close,
   * bounded reconnect with backoff re-runs this — the server validates the
   * session and returns authoritative state via the `resume` event, so the
   * UI recovers without duplicating questions or restarting the interview.
   * The audio pipeline (AudioContext/mic/worklet) is created once in start()
   * inside the user gesture; reconnects only re-establish the socket.
   */
  private openSocket(): void {
    this.ws = new WebSocket(this.url)
    this.ws.binaryType = 'arraybuffer'
    this.ws.onmessage = (ev) => this.handleMessage(ev)
    this.ws.onopen = () => {
      // Re-arm heartbeat on every (re)connect.
      this.armHeartbeat()
      if (this.reconnectAttempts > 0) {
        this.reconnectAttempts = 0
        this.handlers.onReconnected?.()
      }
    }
    this.ws.onclose = () => {
      // Any close — server-completed session, network drop, or cancel — must
      // stop local playback immediately: buffered interviewer audio must not
      // keep playing after the connection/session is gone.
      this.currentGeneration = -1
      this.pendingPlaybackGeneration = -1
      this.flushPlayback()
      this.clearHeartbeat()
      if (this.closedByUser) {
        this.state = 'idle'
        this.handlers.onClosed?.()
        return
      }
      if (this.state === 'completed' || this.state === 'cancelled') {
        this.handlers.onClosed?.()
        return
      }
      // R14: unexpected close -> bounded reconnect with exponential backoff.
      // No duplicate session is created: reconnect targets the SAME URL, the
      // server validates the session and returns authoritative state.
      if (this.reconnectAttempts < this.maxReconnectAttempts) {
        const attempt = this.reconnectAttempts + 1
        this.reconnectAttempts = attempt
        const delay = this.reconnectBaseDelayMs * 2 ** (attempt - 1)
        this.state = 'reconnecting'
        this.handlers.onState?.('reconnecting')
        this.handlers.onReconnecting?.()
        this.reconnectTimer = setTimeout(() => this.openSocket(), delay)
      } else {
        this.state = 'idle'
        this.handlers.onError?.(
          'reconnect_failed',
          'Voice connection lost. Reconnect attempts exhausted — start the interview again.',
        )
        this.handlers.onClosed?.()
      }
    }
  }

  private armHeartbeat(): void {
    this.clearHeartbeat()
    // H heartbeat: keepalive probe so the server can detect liveness and
    // the connection survives proxies. Server answers heartbeat_ack.
    this.heartbeat = setInterval(() => this.sendControl('heartbeat'), 15000)
  }

  private clearHeartbeat(): void {
    if (this.heartbeat) {
      clearInterval(this.heartbeat)
      this.heartbeat = undefined
    }
  }

  private clearReconnectTimer(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = undefined
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

  /**
   * Tear down WITHOUT a WS control message: used when the session is already
   * terminal server-side (e.g. cancelled via the HTTP/SSE path) — the server
   * state is authoritative; this client only stops its own audio + connection
   * so interviewer TTS cannot keep playing after the session is cancelled.
   */
  async disconnect(): Promise<void> {
    this.closedByUser = true
    await this.teardown()
    this.state = 'idle'
    this.handlers.onClosed?.()
  }

  private async teardown(): Promise<void> {
    this.closedByUser = true
    this.clearHeartbeat()
    this.clearReconnectTimer()
    this.captureNode?.disconnect()
    this.captureNode = null
    this.stream?.getTracks().forEach((t) => t.stop())
    this.stream = null
    if (this.ws && this.ws.readyState <= WebSocket.OPEN) this.ws.close()
    this.ws = null
    // Flush playback buffer + close context (no stale audio).
    this.flushPlayback()
    this.currentGeneration = -1
    this.pendingPlaybackGeneration = -1
    if (this.audioCtx) {
      await this.audioCtx.close()
      this.audioCtx = null
    }
  }

  // -- controls -------------------------------------------------------------

  sendControl(type: string, extra: Record<string, unknown> = {}): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type, ...extra }))
    }
  }

  /**
   * Speaker-integrity handshake: called only when the playback queue has
   * ACTUALLY drained (or nothing was queued). Tells the server that real
   * playback finished, so it can authoritatively open LISTENING. The server
   * ignores stale generations, so a late ack can never unlock capture.
   */
  private notifyPlaybackComplete(): void {
    const gen = this.pendingPlaybackGeneration
    if (
      this.ws?.readyState === WebSocket.OPEN &&
      gen >= 0 &&
      gen === this.currentGeneration
    ) {
      this.pendingPlaybackGeneration = -1
      this.sendControl('playback_complete', { generation: gen })
    }
  }

  /** Barge-in: clear local playback NOW and tell the server to cancel TTS. */
  interrupt(): void {
    // H.7: invalidate current generation so any in-flight chunk is dropped.
    this.currentGeneration = -1
    this.pendingPlaybackGeneration = -1
    this.flushPlayback()
    this.sendControl('interrupt')
  }

  /** Manual turn completion (H.2 manual mechanism). */
  doneSpeaking(): void {
    this.sendControl('end_turn')
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
      this.enqueuePlayback(ev.data as ArrayBuffer)
    }
  }

  private dispatch(payload: VoiceEvent): void {
    switch (payload.type) {
      case 'state':
        this.state = payload.state ?? 'idle'
        if (
          payload.state === 'interrupted' ||
          payload.state === 'cancelled' ||
          payload.state === 'paused' ||
          payload.state === 'completed' ||
          payload.state === 'error'
        ) {
          // ANY terminal/abandoned server state kills local playback
          // immediately: stop/cancel/end/error must never leave queued
          // interviewer audio sounding.
          this.currentGeneration = -1
          this.pendingPlaybackGeneration = -1
          this.flushPlayback()
        }
        this.handlers.onState?.(this.state)
        break
      case 'question':
        this.handlers.onQuestion?.({
          id: payload.question_id ?? 0,
          text: payload.text ?? '',
          difficulty: payload.difficulty ?? 'medium',
          source: payload.source ?? null,
          source_ref: payload.source_ref ?? null,
        })
        break
      case 'resume':
        // Phase H: server resync on reconnect — restore the active question
        // so the UI can continue the session in progress.
        this.handlers.onResume?.({
          id: payload.question_id ?? 0,
          text: payload.question ?? payload.text ?? '',
          difficulty: payload.difficulty ?? 'medium',
        })
        break
      case 'heartbeat_ack':
        // Keepalive acknowledgement; no UI action required.
        break
      case 'partial_transcript':
        this.handlers.onPartial?.(payload.text ?? '')
        break
      case 'final_transcript':
        this.handlers.onFinalTranscript?.(payload.text ?? '')
        break
      case 'evaluation':
        this.handlers.onEvaluation?.(payload.overall ?? null, payload.answer_id)
        break
      case 'answer_submitted':
        this.handlers.onAnswerSubmitted?.(payload.answer_id)
        break
      case 'turn_ended':
        this.handlers.onTurnEnded?.()
        break
      case 'tts_start':
        // H.7: remember the active generation; only this generation plays.
        this.currentGeneration = payload.generation ?? -1
        this.pendingPlaybackGeneration = payload.generation ?? -1
        this.handlers.onTTSStart?.(payload.generation)
        break
      case 'tts_stop':
        // H.7: the generation stays valid for QUEUED playback — chunks already
        // received must finish playing. Only interrupt/cancel flushes the
        // queue; a stale generation is dropped at enqueue time. When the
        // queue has fully drained, notifyPlaybackComplete() unlocks the
        // server's LISTENING state (speaker-integrity handshake).
        this.handlers.onTTSStop?.(payload.generation)
        if (this.playbackQueue.length === 0 && this.activeSources.size === 0) {
          this.notifyPlaybackComplete()
        }
        break
      case 'error':
        this.handlers.onError?.(payload.code ?? 'error', payload.message ?? 'Voice error')
        break
    }
  }

  // -- playback (H.6/H.7 + gapless scheduling) ------------------------------

  /**
   * AudioContext clock (seconds) when the next buffer may start. Scheduled
   * start times, not onended-chaining, drive playback: chaining a new
   * AudioBufferSourceNode after each onended leaves an inter-node scheduling
   * gap (~5-20ms at 5Hz for 200ms chunks) which audibly cracks/click at
   * every chunk boundary. Pre-scheduling consecutive nodes keeps PCM
   * sample-continuous across the whole utterance.
   */
  private nextPlaybackAt = 0
  private activeSources = new Set<AudioBufferSourceNode>()

  private enqueuePlayback(data: ArrayBuffer): void {
    if (!this.audioCtx || this.audioCtx.state !== 'running') return
    // H.7: never accept audio outside an active, current TTS generation.
    if (this.state !== 'speaking' || this.currentGeneration < 0) return
    const pcm = new Int16Array(data)
    const buffer = this.audioCtx.createBuffer(1, pcm.length, PLAYBACK_SAMPLE_RATE)
    const channel = buffer.getChannelData(0)
    for (let i = 0; i < pcm.length; i++) channel[i] = pcm[i] / 32768
    this.playbackQueue.push(buffer)
    this.scheduleQueuedPlayback()
  }

  private scheduleQueuedPlayback(): void {
    const ctx = this.audioCtx
    if (!ctx || ctx.state !== 'running') return
    // H.7: stop scheduling once the stream is no longer current.
    if (this.state !== 'speaking' || this.currentGeneration < 0) {
      this.playbackQueue = []
      return
    }
    const now = ctx.currentTime
    let t = Math.max(this.nextPlaybackAt, now + 0.04) // 40ms lookahead (absorbs jitter)
    while (this.playbackQueue.length > 0) {
      const buf = this.playbackQueue.shift()
      if (!buf) break
      const src = ctx.createBufferSource()
      src.buffer = buf
      src.connect(ctx.destination)
      src.onended = () => {
        this.activeSources.delete(src)
        // Real playback completion: queue empty AND every scheduled node ended
        // -> unlock the server's LISTENING (speaker-integrity handshake).
        if (this.activeSources.size === 0 && this.playbackQueue.length === 0) {
          this.notifyPlaybackComplete()
        }
      }
      src.start(t)
      this.activeSources.add(src)
      t += buf.duration
      this.nextPlaybackAt = t
    }
  }

  /** Stop all in-flight playback immediately (interrupt/pause/cancel). */
  private flushPlayback(): void {
    for (const src of this.activeSources) {
      try {
        src.stop()
      } catch {
        /* already stopped */
      }
    }
    this.activeSources.clear()
    this.playbackQueue = []
    this.nextPlaybackAt = 0
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
