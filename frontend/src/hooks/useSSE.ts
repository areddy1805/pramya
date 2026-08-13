// SSE hook: typed interview event stream (GET /interviews/{id}/events).
// fetch + ReadableStream parsing, AbortController, reconnect with backoff.

import { useEffect, useRef, useState } from 'react'

export interface SSEEvent {
  type: string
  data: Record<string, unknown>
}

interface Options {
  enabled?: boolean
  onEvent?: (event: SSEEvent) => void
  reconnectDelayMs?: number
}

export function useSSE(path: string, options: Options = {}) {
  const { enabled = true, onEvent, reconnectDelayMs = 2000 } = options
  const [connected, setConnected] = useState(false)
  const onEventRef = useRef(onEvent)
  onEventRef.current = onEvent

  useEffect(() => {
    if (!enabled) return
    let controller: AbortController | null = null
    let stopped = false
    let timer: ReturnType<typeof setTimeout> | null = null

    async function connect() {
      if (stopped) return
      controller = new AbortController()
      setConnected(false)
      try {
        const res = await fetch(path, { signal: controller.signal, headers: { Accept: 'text/event-stream' } })
        if (!res.ok || !res.body) throw new Error(`SSE HTTP ${res.status}`)
        setConnected(true)
        const reader = res.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''
        // eslint-disable-next-line no-constant-condition
        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })
          const events = buffer.split('\n\n')
          buffer = events.pop() ?? ''
          for (const raw of events) {
            const parsed = parseEvent(raw)
            if (parsed) onEventRef.current?.(parsed)
          }
        }
      } catch (err) {
        if (stopped) return
        if (err instanceof DOMException && err.name === 'AbortError') return
        setConnected(false)
        timer = setTimeout(connect, reconnectDelayMs)
      }
    }

    function parseEvent(raw: string): SSEEvent | null {
      let type = 'message'
      const dataLines: string[] = []
      for (const line of raw.split('\n')) {
        if (line.startsWith(':')) continue
        if (line.startsWith('event:')) type = line.slice(6).trim()
        else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
      }
      const payload = dataLines.join('\n')
      if (!payload) return null
      try {
        return { type, data: JSON.parse(payload) as Record<string, unknown> }
      } catch {
        return null
      }
    }

    void connect()
    return () => {
      stopped = true
      if (timer) clearTimeout(timer)
      controller?.abort()
    }
  }, [path, enabled, reconnectDelayMs])

  return { connected }
}
