import { http, HttpResponse } from 'msw'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { API } from '../../test/mocks/handlers'
import { server } from '../../test/mocks/server'
import * as webApp from '../telegram/webApp'
import { apiFetch, buildUrl } from './client'

vi.mock('../telegram/webApp', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../telegram/webApp')>()),
  getInitDataRaw: vi.fn(() => 'mock-init-data'),
}))

function capture() {
  const seen: { headers?: Headers; credentials?: RequestCredentials; body?: unknown } = {}
  server.use(
    http.all(`${API}/internal/thing`, async ({ request }) => {
      seen.headers = request.headers
      seen.credentials = request.credentials
      // A multipart body is not read: jsdom's File cannot be streamed by Node's fetch.
      const type = request.headers.get('content-type') ?? ''
      seen.body =
        request.method === 'GET' || type.startsWith('multipart') ? null : await request.text()
      return HttpResponse.json({})
    }),
  )
  return seen
}

afterEach(() => vi.mocked(webApp.getInitDataRaw).mockReturnValue('mock-init-data'))

describe('apiFetch for admins', () => {
  it('uses initData inside Telegram and needs no CSRF header there', async () => {
    const seen = capture()

    await apiFetch('/internal/thing', { method: 'POST', body: {}, admin: true })

    expect(seen.headers?.get('authorization')).toBe('tma mock-init-data')
    expect(seen.headers?.get('x-requested-with')).toBeNull()
  })

  it('relies on the session cookie in a browser and marks writes against CSRF', async () => {
    vi.mocked(webApp.getInitDataRaw).mockReturnValue('')
    const seen = capture()

    await apiFetch('/internal/thing', { method: 'PATCH', body: { a: 1 }, admin: true })

    expect(seen.headers?.get('authorization')).toBeNull()
    expect(seen.headers?.get('x-requested-with')).toBe('admin')
    expect(seen.credentials).toBe('include')
  })

  it('sends no CSRF header on browser reads', async () => {
    vi.mocked(webApp.getInitDataRaw).mockReturnValue('')
    const seen = capture()

    await apiFetch('/internal/thing', { admin: true })

    expect(seen.headers?.get('x-requested-with')).toBeNull()
  })

  // The trailing space of "tma " is trimmed by Headers; the API answers 401 either way.
  it('keeps sending an (empty) tma header for customers outside Telegram', async () => {
    vi.mocked(webApp.getInitDataRaw).mockReturnValue('')
    const seen = capture()

    await apiFetch('/internal/thing')

    expect(seen.headers?.get('authorization')).toBe('tma')
  })

  it('sends FormData as multipart, letting the browser set the boundary', async () => {
    const seen = capture()
    const form = new FormData()
    form.append('file', new File(['x'], 'a.jpg', { type: 'image/jpeg' }))

    await apiFetch('/internal/thing', { method: 'POST', body: form, admin: true })

    expect(seen.headers?.get('content-type')).toMatch(/^multipart\/form-data; boundary=/)
  })
})

describe('buildUrl', () => {
  it('repeats array parameters and skips undefined ones', () => {
    const url = buildUrl('http://api.test', '/x', {
      status: ['paid', 'shipped'],
      q: undefined,
      n: 0,
    })

    expect(url.search).toBe('?status=paid&status=shipped&n=0')
  })
})
