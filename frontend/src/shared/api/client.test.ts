import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { API } from '../../test/mocks/handlers'
import { server } from '../../test/mocks/server'
import { ApiError, apiFetch } from './client'

describe('apiFetch', () => {
  it('sends the Telegram initData as a tma Authorization header', async () => {
    let authorization: string | null = null
    server.use(
      http.get(`${API}/ping`, ({ request }) => {
        authorization = request.headers.get('authorization')
        return HttpResponse.json({ ok: true })
      }),
    )

    await apiFetch('/ping')

    expect(authorization).toBe('tma mock-init-data')
  })

  it('serialises the body and omits undefined query params', async () => {
    let received: { url: string; body: unknown } | null = null
    server.use(
      http.post(`${API}/things`, async ({ request }) => {
        received = { url: request.url, body: await request.json() }
        return HttpResponse.json({})
      }),
    )

    await apiFetch('/things', {
      method: 'POST',
      body: { a: 1 },
      params: { keep: 'yes', skip: undefined },
    })

    expect(received).toEqual({ url: `${API}/things?keep=yes`, body: { a: 1 } })
  })

  it('throws an ApiError carrying status and detail on a non-2xx response', async () => {
    server.use(
      http.get(`${API}/boom`, () => HttpResponse.json({ detail: 'nope' }, { status: 409 })),
    )

    const error = await apiFetch('/boom').catch((caught: unknown) => caught)

    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(409)
    expect((error as ApiError).detail).toEqual({ detail: 'nope' })
  })

  it('returns undefined for a 204 response', async () => {
    server.use(http.delete(`${API}/gone`, () => new HttpResponse(null, { status: 204 })))

    await expect(apiFetch('/gone', { method: 'DELETE' })).resolves.toBeUndefined()
  })
})
