import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { API } from '../../../test/mocks/handlers'
import { server } from '../../../test/mocks/server'
import { renderScreen } from '../../../test/test-utils'
import { CheckoutScreen } from './CheckoutScreen'

const { confirmPayment } = vi.hoisted(() => ({ confirmPayment: vi.fn() }))

vi.mock('@stripe/stripe-js', () => ({ loadStripe: vi.fn(() => Promise.resolve({})) }))
vi.mock('@stripe/react-stripe-js', () => ({
  Elements: ({ children }: { children: ReactNode }) => children,
  PaymentElement: () => <div data-testid="payment-element" />,
  useStripe: () => ({ confirmPayment }),
  useElements: () => ({}),
}))

const routeOptions = {
  route: '/checkout',
  path: '/checkout',
  extraRoutes: [{ path: '/orders/:orderId', element: <div>order page</div> }],
}

async function fillAddress(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByPlaceholderText('Street address'), 'Alexanderplatz 1')
  await user.type(screen.getByPlaceholderText('City'), 'Berlin')
  await user.type(screen.getByPlaceholderText('Postal code'), '10178')
  await user.type(screen.getByPlaceholderText('Country'), 'DE')
  await user.type(screen.getByPlaceholderText('Phone'), '+491234567')
}

function stubCheckout(onRequest?: (body: unknown) => void) {
  server.use(
    http.post(`${API}/checkout`, async ({ request }) => {
      onRequest?.(await request.json())
      return HttpResponse.json({
        order_id: 77,
        client_secret: 'cs_test_secret',
        total: '24.99',
        currency: 'EUR',
      })
    }),
  )
}

describe('CheckoutScreen', () => {
  beforeEach(() => {
    confirmPayment.mockReset()
  })

  it('does not submit until the required address fields are filled', async () => {
    const user = userEvent.setup()
    let requested = false
    stubCheckout(() => {
      requested = true
    })
    renderScreen(<CheckoutScreen />, routeOptions)

    await user.click(screen.getByRole('button', { name: 'Continue to payment' }))

    expect(requested).toBe(false)
    expect(screen.queryByTestId('payment-element')).not.toBeInTheDocument()
  })

  it('posts the address then shows the payment step', async () => {
    const user = userEvent.setup()
    let body: unknown = null
    stubCheckout((received) => {
      body = received
    })
    renderScreen(<CheckoutScreen />, routeOptions)

    await fillAddress(user)
    await user.click(screen.getByRole('button', { name: 'Continue to payment' }))

    expect(await screen.findByTestId('payment-element')).toBeInTheDocument()
    expect(body).toMatchObject({
      delivery_address: { street: 'Alexanderplatz 1', city: 'Berlin', postal_code: '10178' },
    })
  })

  it('confirms the payment and lands on the order once it is no longer pending', async () => {
    const user = userEvent.setup()
    confirmPayment.mockResolvedValue({})
    stubCheckout()
    renderScreen(<CheckoutScreen />, routeOptions)

    await fillAddress(user)
    await user.click(screen.getByRole('button', { name: 'Continue to payment' }))
    await user.click(await screen.findByRole('button', { name: 'Pay now' }))

    expect(await screen.findByText('order page')).toBeInTheDocument()
    expect(confirmPayment).toHaveBeenCalledTimes(1)
  })

  it('stays on the payment step and shows the card error when payment is declined', async () => {
    const user = userEvent.setup()
    confirmPayment.mockResolvedValue({ error: { message: 'Your card was declined.' } })
    stubCheckout()
    renderScreen(<CheckoutScreen />, routeOptions)

    await fillAddress(user)
    await user.click(screen.getByRole('button', { name: 'Continue to payment' }))
    await user.click(await screen.findByRole('button', { name: 'Pay now' }))

    expect(await screen.findByText('Your card was declined.')).toBeInTheDocument()
    expect(screen.queryByText('order page')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Pay now' })).toBeEnabled()
  })

  it('shows an error and keeps the form when creating the order fails', async () => {
    const user = userEvent.setup()
    server.use(http.post(`${API}/checkout`, () => new HttpResponse(null, { status: 500 })))
    renderScreen(<CheckoutScreen />, routeOptions)

    await fillAddress(user)
    await user.click(screen.getByRole('button', { name: 'Continue to payment' }))

    expect(await screen.findByText('Something went wrong')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Street address')).toHaveValue('Alexanderplatz 1')
  })
})
