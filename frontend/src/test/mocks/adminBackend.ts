import { http, HttpResponse } from 'msw'

import type { AdminRole } from '../../features/admin/types'
import {
  adminAttributes,
  adminCategories,
  adminCouriers,
  adminMe,
  adminOrder,
  adminOrderList,
  adminProduct,
  adminProductList,
  admins,
  adminSellers,
  sellerLedger,
  sellerOrder,
  sellerOrderList,
  adminShipments,
  courierLocations,
  summary,
} from '../adminFixtures'
import { API } from './handlers'
import { server } from './server'

const I = `${API}/internal`

export interface RecordedRequest {
  method: string
  path: string
  search: URLSearchParams
  body: unknown
  headers: Headers
}

/**
 * Happy-path admin API for screen tests: every read returns the fixtures, every write answers
 * with something plausible and is recorded, so tests can assert what was sent. Tests override
 * single endpoints with `server.use` for failures.
 */
export function stubAdminBackend(role: AdminRole | 401 | 403 = 'owner') {
  const requests: RecordedRequest[] = []

  async function record(request: Request): Promise<unknown> {
    const url = new URL(request.url)
    let body: unknown = null
    const type = request.headers.get('content-type') ?? ''
    if (type.startsWith('multipart/form-data')) {
      // Not read: jsdom's File cannot be streamed by Node's fetch, so the body would hang.
      body = 'multipart'
    } else if (request.method !== 'GET') {
      const text = await request.clone().text()
      body = text ? JSON.parse(text) : null
    }
    requests.push({
      method: request.method,
      path: url.pathname.replace('/internal', ''),
      search: url.searchParams,
      body,
      headers: request.headers,
    })
    return body
  }

  server.use(
    http.get(`${I}/me`, () =>
      typeof role === 'number'
        ? HttpResponse.json({ detail: 'nope' }, { status: role })
        : HttpResponse.json(adminMe(role)),
    ),
    http.get(`${I}/stats/summary`, async ({ request }) => {
      await record(request)
      return HttpResponse.json(summary)
    }),
    http.get(`${I}/categories`, () => HttpResponse.json(adminCategories)),
    http.get(`${I}/attributes`, () => HttpResponse.json(adminAttributes)),
    http.get(`${I}/products`, async ({ request }) => {
      await record(request)
      return HttpResponse.json({ items: adminProductList, total: adminProductList.length })
    }),
    http.get(`${I}/products/:id`, () => HttpResponse.json(adminProduct)),
    http.get(`${I}/orders`, async ({ request }) => {
      await record(request)
      return HttpResponse.json({ items: adminOrderList, total: adminOrderList.length })
    }),
    http.get(`${I}/orders/:id`, ({ params }) =>
      HttpResponse.json(adminOrder({ id: Number(params.id) })),
    ),
    http.get(`${I}/couriers`, () => HttpResponse.json(adminCouriers)),
    http.get(`${I}/couriers/locations`, () => HttpResponse.json(courierLocations)),
    http.get(`${I}/shipments`, () => HttpResponse.json(adminShipments)),
    http.get(`${I}/admins`, () => HttpResponse.json(admins)),
    http.get(`${I}/sellers`, () => HttpResponse.json(adminSellers)),
    http.get(`${I}/sellers/:id/ledger`, () => HttpResponse.json(sellerLedger)),
    http.get(`${I}/seller/earnings`, () => HttpResponse.json(sellerLedger)),
    http.get(`${I}/seller/orders`, () =>
      HttpResponse.json({ items: sellerOrderList, total: sellerOrderList.length }),
    ),
    http.get(`${I}/seller/orders/:id`, ({ params }) =>
      HttpResponse.json(sellerOrder({ id: Number(params.id) })),
    ),
    http.post(`${I}/orders/:id/ready`, async ({ request, params }) => {
      await record(request)
      return HttpResponse.json({ order_id: Number(params.id), ready_at: '2026-09-24T11:00:00Z' })
    }),

    http.post(`${I}/products`, async ({ request }) => {
      const body = (await record(request)) as object
      return HttpResponse.json({ ...adminProduct, ...body, id: 99 }, { status: 201 })
    }),
    http.post(`${I}/orders/:id/cancel`, async ({ request, params }) => {
      await record(request)
      return HttpResponse.json(
        adminOrder({
          id: Number(params.id),
          status: 'cancelled',
          can_cancel: false,
          payment: { status: 'succeeded', amount: '34.97', refund_status: 'pending' },
        }),
      )
    }),
    http.post(`${I}/orders/:id/refund`, async ({ request, params }) => {
      await record(request)
      return HttpResponse.json(
        adminOrder({
          id: Number(params.id),
          status: 'cancelled',
          can_cancel: false,
          payment: { status: 'succeeded', amount: '34.97', refund_status: 'succeeded' },
        }),
      )
    }),
    http.post(`${I}/products/:id/images`, async ({ request, params }) => {
      await record(request)
      return HttpResponse.json(
        {
          id: 77,
          product_id: Number(params.id),
          variant_id: null,
          url: '/media/x.webp',
          position: 2,
        },
        { status: 201 },
      )
    }),
    // Generic writes: record and echo.
    http.post(`${I}/*`, async ({ request }) => {
      const body = await record(request)
      return HttpResponse.json({ id: 100, ...(body as object) }, { status: 201 })
    }),
    http.patch(`${I}/*`, async ({ request }) => {
      const body = await record(request)
      return HttpResponse.json({ id: 100, ...(body as object) })
    }),
    http.delete(`${I}/*`, async ({ request }) => {
      await record(request)
      return new HttpResponse(null, { status: 204 })
    }),
  )

  return {
    requests,
    /** Writes only (and summary/list reads that were recorded), in order. */
    writes: () => requests.filter((r) => r.method !== 'GET'),
  }
}
