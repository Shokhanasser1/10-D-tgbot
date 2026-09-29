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

type ParamValue = string | number | boolean | undefined | readonly (string | number)[]

export interface ApiFetchOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'
  /** JSON-serialised, except FormData, which is sent as multipart as is. */
  body?: unknown
  /** Arrays repeat the parameter: `{ status: ['a', 'b'] }` -> `?status=a&status=b`. */
  params?: Record<string, ParamValue>
  /**
   * Admin requests. Outside Telegram there is no initData, so the admin session cookie is the
   * credential; state-changing requests then carry the header the API requires against CSRF.
   */
  admin?: boolean
  /** Extra request headers. */
  headers?: Record<string, string>
}

const SAFE_METHODS = new Set(['GET', 'HEAD'])

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
    if (value === undefined) continue
    if (Array.isArray(value)) {
      for (const item of value) url.searchParams.append(key, String(item))
    } else {
      url.searchParams.set(key, String(value))
    }
  }
  return url
}

export async function apiFetch<T>(path: string, options: ApiFetchOptions = {}): Promise<T> {
  const { method = 'GET', body, params, admin = false, headers: extraHeaders = {} } = options

  const url = buildUrl(API_BASE_URL, path, params)
  const initData = getInitDataRaw()
  const isForm = body instanceof FormData

  const headers: Record<string, string> = {}
  // The browser sets a multipart Content-Type with its boundary itself.
  if (!isForm) headers['Content-Type'] = 'application/json'
  // Customers always send initData (empty outside Telegram: the API then answers 401). For
  // admins an empty value would shadow the session cookie, so it is left out instead.
  if (!admin || initData) headers.Authorization = `tma ${initData}`
  if (admin && !initData && !SAFE_METHODS.has(method)) headers['X-Requested-With'] = 'admin'
  Object.assign(headers, extraHeaders)

  const response = await fetch(url.toString(), {
    method,
    headers,
    body: isForm ? body : body !== undefined ? JSON.stringify(body) : undefined,
    // Cookies only matter for admins; in development the API is on another port of the same
    // site, where the SameSite=Strict session cookie is still sent with "include".
    credentials: admin ? 'include' : 'same-origin',
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
