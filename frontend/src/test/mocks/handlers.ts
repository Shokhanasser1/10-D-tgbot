import { http, HttpResponse } from 'msw'

import { cart, categories, orderDetail, orders, productDetail, products } from '../fixtures'

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
  http.get(`${API}/orders`, () => HttpResponse.json(orders)),
  http.get(`${API}/orders/:id`, () => HttpResponse.json(orderDetail)),
]
