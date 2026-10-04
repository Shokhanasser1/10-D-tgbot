import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { useLocation } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { cart, productDetail } from '../../../test/fixtures'
import { API } from '../../../test/mocks/handlers'
import { server } from '../../../test/mocks/server'
import { renderScreen } from '../../../test/test-utils'
import { ProductDetailScreen } from './ProductDetailScreen'

const routeOptions = {
  route: '/products/1',
  path: '/products/:productId',
  extraRoutes: [{ path: '/cart', element: <div>cart page</div> }],
}

describe('ProductDetailScreen', () => {
  it('shows the product with its first variant selected by default', async () => {
    renderScreen(<ProductDetailScreen />, routeOptions)

    expect(
      await screen.findByRole('heading', { name: 'Velvet Matte Lipstick' }),
    ).toBeInTheDocument()
    expect(screen.getByText('Long-lasting matte finish.')).toBeInTheDocument()
    expect(screen.getByText(/19[.,]99/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Add to cart' })).toBeEnabled()
  })

  it('updates the price when another variant is picked', async () => {
    const user = userEvent.setup()
    renderScreen(<ProductDetailScreen />, routeOptions)
    await screen.findByRole('heading', { name: 'Velvet Matte Lipstick' })

    await user.click(screen.getByRole('button', { name: 'berry' }))

    expect(screen.getByText(/22[.,]00/)).toBeInTheDocument()
  })

  it('adds the picked variant to the cart and goes to the cart', async () => {
    const user = userEvent.setup()
    let posted: unknown = null
    server.use(
      http.post(`${API}/cart/items`, async ({ request }) => {
        posted = await request.json()
        return HttpResponse.json(cart, { status: 201 })
      }),
    )
    renderScreen(<ProductDetailScreen />, routeOptions)
    await screen.findByRole('heading', { name: 'Velvet Matte Lipstick' })

    await user.click(screen.getByRole('button', { name: 'berry' }))
    await user.click(screen.getByRole('button', { name: 'Add to cart' }))

    expect(await screen.findByText('cart page')).toBeInTheDocument()
    expect(posted).toEqual({ variant_id: 13, qty: 1 })
  })

  it('disables the action and says so when the selected variant is out of stock', async () => {
    const soldOut = {
      ...productDetail,
      variants: productDetail.variants.map((variant, index) =>
        index === 0 ? { ...variant, stock_qty: 0 } : variant,
      ),
    }
    server.use(http.get(`${API}/catalog/products/:id`, () => HttpResponse.json(soldOut)))
    renderScreen(<ProductDetailScreen />, routeOptions)

    const button = await screen.findByRole('button', { name: 'Out of stock' })

    expect(button).toBeDisabled()
  })

  it('shows an error with retry when the product fails to load', async () => {
    server.use(
      http.get(`${API}/catalog/products/:id`, () => new HttpResponse(null, { status: 500 })),
    )
    renderScreen(<ProductDetailScreen />, routeOptions)

    expect(await screen.findByText('Something went wrong')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
  })
})

function Where() {
  const location = useLocation()
  return <div>at {location.pathname + location.search}</div>
}

describe('ProductDetailScreen: sellers (Spec 9)', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('names the seller and opens their products', async () => {
    const user = userEvent.setup()
    renderScreen(<ProductDetailScreen />, {
      ...routeOptions,
      extraRoutes: [{ path: '/', element: <Where /> }],
    })

    await user.click(await screen.findByRole('button', { name: 'Seller: Lola Beauty' }))

    expect(await screen.findByText('at /?seller=7')).toBeInTheDocument()
  })

  function conflictThenOk(posted: unknown[]) {
    server.use(
      http.get(`${API}/cart/items`, () =>
        HttpResponse.json({ ...cart, seller: { id: 8, name: 'Anor' } }),
      ),
      http.post(`${API}/cart/items`, async ({ request }) => {
        const body = (await request.json()) as { replace_cart?: boolean }
        posted.push(body)
        return body.replace_cart
          ? HttpResponse.json(cart, { status: 201 })
          : HttpResponse.json(
              { detail: "The cart holds another seller's products", code: 'cart_other_seller' },
              { status: 409 },
            )
      }),
    )
  }

  it('offers to empty a cart of another seller, then adds the product', async () => {
    const user = userEvent.setup()
    const posted: unknown[] = []
    conflictThenOk(posted)
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true)
    renderScreen(<ProductDetailScreen />, routeOptions)
    await screen.findByRole('heading', { name: 'Velvet Matte Lipstick' })

    await user.click(screen.getByRole('button', { name: 'Add to cart' }))

    expect(await screen.findByText('cart page')).toBeInTheDocument()
    expect(confirm).toHaveBeenCalledWith(
      'Your cart has products from Anor. Empty it and add this product?',
    )
    expect(posted).toEqual([
      { variant_id: 11, qty: 1 },
      { variant_id: 11, qty: 1, replace_cart: true },
    ])
  })

  it('keeps the cart when the customer declines', async () => {
    const user = userEvent.setup()
    const posted: unknown[] = []
    conflictThenOk(posted)
    vi.spyOn(window, 'confirm').mockReturnValue(false)
    renderScreen(<ProductDetailScreen />, routeOptions)
    await screen.findByRole('heading', { name: 'Velvet Matte Lipstick' })

    await user.click(screen.getByRole('button', { name: 'Add to cart' }))

    await waitFor(() => expect(posted).toHaveLength(1))
    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(posted).toHaveLength(1)
    expect(screen.queryByText('cart page')).not.toBeInTheDocument()
  })
})
