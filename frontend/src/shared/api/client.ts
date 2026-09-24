import { getInitDataRaw } from '../telegram/webApp'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL as string

export class ApiError extends Error {
  status: number
  detail: unknown

  constructor(status: number, detail: unknown) {
    super(typeof detail === 'string' ? detail : `Request failed with status ${status}`)
    this.status = status
    this.detail = detail
  }
}

interface ApiFetchOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'
  body?: unknown
  params?: Record<string, string | number | undefined>
}

/**
 * Joins base and path by string concatenation, not `new URL(path, base)`: the latter drops
 * the base's own path, so a same-origin base like "/api" would silently be lost.
 * `origin` resolves a relative base such as "/api" to an absolute URL.
 */
export function buildUrl(
  base: string,
  path: string,
  params: ApiFetchOptions['params'] = {},
  origin: string = window.location.origin,
): URL {
  const url = new URL(`${base.replace(/\/$/, '')}${path}`, origin)
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined) url.searchParams.set(key, String(value))
  }
  return url
}

export async function apiFetch<T>(path: string, options: ApiFetchOptions = {}): Promise<T> {
  const { method = 'GET', body, params } = options

  const url = buildUrl(API_BASE_URL, path, params)

  const response = await fetch(url.toString(), {
    method,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `tma ${getInitDataRaw()}`,
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })

  if (!response.ok) {
    let detail: unknown
    try {
      detail = await response.json()
    } catch {
      detail = await response.text()
    }
    throw new ApiError(response.status, detail)
  }

  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}
