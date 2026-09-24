import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { cart, emptyCart } from '../../../test/fixtures'
import { API } from '../../../test/mocks/handlers'
import { server } from '../../../test/mocks/server'
import { renderScreen } from '../../../test/test-utils'
import { CartScreen } from './CartScreen'

const routeOptions = {
  route: '/cart',
  path: '/cart',
  extraRoutes: [{ path: '/checkout', element: <div>checkout page</div> }],
}

describe('CartScreen', () => {
  it('lists the items with their quantity and the subtotal', async () => {
    renderScreen(<CartScreen />, routeOptions)

    expect(await screen.findByText('Velvet Matte Lipstick')).toBeInTheDocument()
    expect(screen.getByText('LIP-VELVET-RED')).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument()
    expect(screen.getByText('Subtotal').parentElement).toHaveTextContent(/39[.,]98/)
  })

  it('sends the new quantity when the stepper is used and shows the server result', async () => {
    const user = userEvent.setup()
    let patched: unknown = null
    server.use(
      http.patch(`${API}/cart/items/101`, async ({ request }) => {
        patched = await request.json()
        return HttpResponse.json({
          items: [{ ...cart.items[0], qty: 3, line_total: '59.97' }],
          subtotal: '59.97',
        })
      }),
    )
    renderScreen(<CartScreen />, routeOptions)
    await screen.findByText('Velvet Matte Lipstick')

    await user.click(screen.getByRole('button', { name: 'Increase quantity' }))

    expect(await screen.findByText('3')).toBeInTheDocument()
    expect(patched).toEqual({ qty: 3 })
    expect(screen.getByText('Subtotal').parentElement).toHaveTextContent(/59[.,]97/)
  })

  it('removes an item and falls back to the empty state', async () => {
    const user = userEvent.setup()
    let deleted = false
    server.use(
      http.delete(`${API}/cart/items/101`, () => {
        deleted = true
        return HttpResponse.json(emptyCart)
      }),
    )
    renderScreen(<CartScreen />, routeOptions)
    await screen.findByText('Velvet Matte Lipstick')

    await user.click(screen.getByRole('button', { name: 'Remove item' }))

    expect(await screen.findByText('Your cart is empty')).toBeInTheDocument()
    expect(deleted).toBe(true)
  })

  it('shows the empty state when the cart has no items', async () => {
    server.use(http.get(`${API}/cart/items`, () => HttpResponse.json(emptyCart)))
    renderScreen(<CartScreen />, routeOptions)

    expect(await screen.findByText('Your cart is empty')).toBeInTheDocument()
  })

  it('goes to checkout from the summary', async () => {
    const user = userEvent.setup()
    renderScreen(<CartScreen />, routeOptions)
    await screen.findByText('Velvet Matte Lipstick')

    await user.click(screen.getByRole('button', { name: 'Checkout' }))

    expect(await screen.findByText('checkout page')).toBeInTheDocument()
  })

  it('shows an error with retry when the cart fails to load', async () => {
    server.use(http.get(`${API}/cart/items`, () => new HttpResponse(null, { status: 500 })))
    renderScreen(<CartScreen />, routeOptions)

    expect(await screen.findByText('Something went wrong')).toBeInTheDocument()
  })
})
