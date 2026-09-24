import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { courierProfile } from '../../test/fixtures'
import { API } from '../../test/mocks/handlers'
import { server } from '../../test/mocks/server'
import { ApiError } from '../../shared/api/client'
import { claimDelivery, getCourierProfile } from './api'

describe('getCourierProfile', () => {
  it('returns the profile of a courier', async () => {
    server.use(http.get(`${API}/courier/me`, () => HttpResponse.json(courierProfile)))

    expect(await getCourierProfile()).toEqual(courierProfile)
  })

  it('returns null, not an error, for a customer (403)', async () => {
    expect(await getCourierProfile()).toBeNull()
  })

  it.each([401, 500])(
    'still rejects on %d, so a real failure is not mistaken for "no"',
    async (status) => {
      server.use(http.get(`${API}/courier/me`, () => new HttpResponse(null, { status })))

      await expect(getCourierProfile()).rejects.toBeInstanceOf(ApiError)
    },
  )
})

describe('delivery actions', () => {
  it('POSTs to the shipment-specific path', async () => {
    let seen = ''
    server.use(
      http.post(`${API}/courier/deliveries/:id/:step`, ({ request }) => {
        seen = `${request.method} ${new URL(request.url).pathname}`
        return HttpResponse.json({ shipment_id: 7, order_id: 1, status: 'assigned' })
      }),
    )

    await claimDelivery(7)

    expect(seen).toBe('POST /courier/deliveries/7/claim')
  })
})
