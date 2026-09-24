import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

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
