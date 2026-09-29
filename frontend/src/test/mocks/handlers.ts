import { http, HttpResponse } from 'msw'

import {
  cart,
  categories,
  orderDetail,
  orders,
  poolItems,
  productDetail,
  products,
  trackingProcessing,
} from '../fixtures'

export const API = 'http://api.test'

// Happy-path defaults; individual tests override with server.use(...).
export const handlers = [
  http.get(`${API}/catalog/categories`, () => HttpResponse.json(categories)),
  http.get(`${API}/catalog/products`, ({ request }) => {
    const category = new URL(request.url).searchParams.get('category')
    const visible = category
      ? products.filter((product) => String(product.category_id) === category)
      : products
    return HttpResponse.json(visible)
  }),
  http.get(`${API}/catalog/products/:id`, () => HttpResponse.json(productDetail)),
  http.get(`${API}/cart/items`, () => HttpResponse.json(cart)),
  http.get(`${API}/checkout/methods`, () =>
    HttpResponse.json({ methods: ['stripe'], currency: 'EUR' }),
  ),
  http.get(`${API}/orders`, () => HttpResponse.json(orders)),
  http.get(`${API}/orders/:id`, () => HttpResponse.json(orderDetail)),
  http.get(`${API}/orders/:id/tracking`, () => HttpResponse.json(trackingProcessing)),

  // Couriers. Most users are customers, for whom /courier/me is a plain 403.
  http.get(`${API}/courier/me`, () =>
    HttpResponse.json({ detail: 'Not a courier' }, { status: 403 }),
  ),
  http.get(`${API}/courier/pool`, () => HttpResponse.json(poolItems)),
  http.get(`${API}/courier/deliveries`, () =>
    HttpResponse.json({ location_updated_at: null, deliveries: [] }),
  ),
  // Admins. For everyone else the admin identity endpoint is a plain 403.
  http.get(`${API}/internal/me`, () =>
    HttpResponse.json({ detail: 'Not an admin' }, { status: 403 }),
  ),
  http.post(`${API}/courier/deliveries/:id/:step`, ({ params }) =>
    HttpResponse.json({ shipment_id: Number(params.id), order_id: 0, status: 'assigned' }),
  ),
]
