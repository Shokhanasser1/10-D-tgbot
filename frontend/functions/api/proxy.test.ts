import { afterEach, describe, expect, it, vi } from 'vitest'

import { onRequest } from './[[path]]'

const BACKEND_URL = 'https://backend.test'

function forwardedUrl(fetchMock: ReturnType<typeof vi.fn>): string {
  return String(fetchMock.mock.calls[0][0])
}

async function proxy(url: string, init?: RequestInit) {
  const fetchMock = vi.fn().mockResolvedValue(new Response('ok'))
  vi.stubGlobal('fetch', fetchMock)
  const response = await onRequest({ request: new Request(url, init), env: { BACKEND_URL } })
  return { fetchMock, response }
}

describe('Pages /api proxy', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('strips the /api prefix, because the backend serves its routes from the root', async () => {
    const { fetchMock } = await proxy('https://shop.pages.dev/api/health')

    expect(forwardedUrl(fetchMock)).toBe(`${BACKEND_URL}/health`)
  })

  it('keeps the rest of the path and the query string', async () => {
    const { fetchMock } = await proxy('https://shop.pages.dev/api/catalog/products?limit=5&q=a%20b')

    expect(forwardedUrl(fetchMock)).toBe(`${BACKEND_URL}/catalog/products?limit=5&q=a%20b`)
  })

  it('forwards the Telegram webhook with its method and body', async () => {
    const { fetchMock } = await proxy('https://shop.pages.dev/api/webhooks/telegram', {
      method: 'POST',
      body: '{"update_id":1}',
    })

    expect(forwardedUrl(fetchMock)).toBe(`${BACKEND_URL}/webhooks/telegram`)
    expect(fetchMock.mock.calls[0][1].method).toBe('POST')
  })

  it.each(['/api//evil.test/steal', '/api/\\evil.test/steal', '/api///evil.test'])(
    'never leaves the backend host for %s',
    async (path) => {
      const { fetchMock } = await proxy(`https://shop.pages.dev${path}`)

      expect(new URL(forwardedUrl(fetchMock)).origin).toBe(BACKEND_URL)
    },
  )

  it('leaves paths outside /api (photos without an R2 binding) unchanged', async () => {
    const { fetchMock } = await proxy('https://shop.pages.dev/media/products/ab12.webp')

    expect(forwardedUrl(fetchMock)).toBe(`${BACKEND_URL}/media/products/ab12.webp`)
  })

  it('answers 503 when BACKEND_URL is not set', async () => {
    const response = await onRequest({
      request: new Request('https://shop.pages.dev/api/health'),
      env: {},
    })

    expect(response.status).toBe(503)
  })
})
