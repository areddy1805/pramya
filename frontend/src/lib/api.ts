// Typed API client for the Pramya backend (REST /api/v1).
// Single fetch wrapper: JSON in/out, error-envelope handling, base URL
// from VITE_API_URL (vite dev proxy: /api -> 127.0.0.1:8000).

export interface ApiErrorEnvelope {
  code: string
  message: string
  request_id: string
  details: Record<string, unknown>
}

export class ApiError extends Error {
  code: string
  status: number
  request_id: string
  details: Record<string, unknown>

  constructor(envelope: ApiErrorEnvelope, status: number) {
    super(envelope.message)
    this.name = 'ApiError'
    this.code = envelope.code
    this.status = status
    this.request_id = envelope.request_id
    this.details = envelope.details ?? {}
  }
}

const BASE = import.meta.env.VITE_API_URL ?? ''

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  headers: Record<string, string> = {},
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: {
      Accept: 'application/json',
      ...(body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...headers,
    },
    body: body instanceof FormData ? body : body === undefined ? undefined : JSON.stringify(body),
  })
  if (res.status === 204) return undefined as T
  const data = (await res.json().catch(() => null)) as T | ApiErrorEnvelope
  if (!res.ok) {
    throw new ApiError(
      (data as ApiErrorEnvelope) ?? {
        code: 'http_error',
        message: `HTTP ${res.status}`,
        request_id: '',
        details: {},
      },
      res.status,
    )
  }
  return data as T
}

export const api = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body?: unknown) => request<T>('POST', path, body),
  patch: <T>(path: string, body?: unknown) => request<T>('PATCH', path, body),
  delete: <T>(path: string) => request<T>('DELETE', path),
  put: <T>(path: string, body?: unknown) => request<T>('PUT', path, body),
  upload: <T>(path: string, form: FormData) => request<T>('POST', path, form),
}

// Query-string helper (user_id etc. are query params in this API).
export function qs(params: Record<string, string | number | undefined | null>): string {
  const parts = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== null && v !== '')
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
  return parts.length ? `?${parts.join('&')}` : ''
}
