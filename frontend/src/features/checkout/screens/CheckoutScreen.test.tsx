import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import type { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { API } from '../../../test/mocks/handlers'
import { fireMapClick } from '../../../test/mocks/reactLeaflet'
import { server } from '../../../test/mocks/server'
import { renderScreen } from '../../../test/test-utils'
import { formatClock } from '../../../shared/time/formatClock'
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
        reserved_until: '2026-09-22T10:15:00Z',
      })
    }),
  )
}

describe('CheckoutScreen', () => {
  beforeEach(() => {
    confirmPayment.mockReset()
  })

  afterEach(() => {
    Reflect.deleteProperty(navigator, 'geolocation')
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

  it('tells the customer how long the items are held on the payment step', async () => {
    const user = userEvent.setup()
    stubCheckout()
    renderScreen(<CheckoutScreen />, routeOptions)

    await fillAddress(user)
    await user.click(screen.getByRole('button', { name: 'Continue to payment' }))

    const time = formatClock('2026-09-22T10:15:00Z', 'en')
    expect(
      await screen.findByText(`We hold your items until ${time}. Please pay before then.`),
    ).toBeInTheDocument()
  })

  it('sends the customer back to the cart when items sold out meanwhile', async () => {
    const user = userEvent.setup()
    server.use(
      http.post(`${API}/checkout`, () =>
        HttpResponse.json(
          { detail: 'Insufficient stock for variant X', code: 'insufficient_stock' },
          { status: 409 },
        ),
      ),
    )
    renderScreen(<CheckoutScreen />, {
      ...routeOptions,
      extraRoutes: [...routeOptions.extraRoutes, { path: '/cart', element: <div>cart page</div> }],
    })

    await fillAddress(user)
    await user.click(screen.getByRole('button', { name: 'Continue to payment' }))

    expect(
      await screen.findByText('Some items just sold out. Check your cart and try again.'),
    ).toBeInTheDocument()
    expect(screen.queryByText('Something went wrong')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Back to cart' }))
    expect(await screen.findByText('cart page')).toBeInTheDocument()
  })

  it('says payments are unavailable when the payment provider is down', async () => {
    const user = userEvent.setup()
    server.use(
      http.post(`${API}/checkout`, () =>
        HttpResponse.json(
          { detail: 'Payment provider unavailable', code: 'payment_unavailable' },
          { status: 502 },
        ),
      ),
    )
    renderScreen(<CheckoutScreen />, routeOptions)

    await fillAddress(user)
    await user.click(screen.getByRole('button', { name: 'Continue to payment' }))

    expect(
      await screen.findByText(
        'Payments are unavailable right now. Your cart is saved, please try again later.',
      ),
    ).toBeInTheDocument()
  })

  describe('delivery pin', () => {
    type Body = { delivery_address: Record<string, unknown> }

    function captureBody() {
      const captured: { body: Body | null } = { body: null }
      stubCheckout((received) => {
        captured.body = received as Body
      })
      return captured
    }

    it('is sent with the address when one is placed', async () => {
      const user = userEvent.setup()
      const captured = captureBody()
      renderScreen(<CheckoutScreen />, routeOptions)

      await fillAddress(user)
      await screen.findByTestId('map')
      fireMapClick(52.520008, 13.404954)
      await user.click(screen.getByRole('button', { name: 'Continue to payment' }))

      expect(await screen.findByTestId('payment-element')).toBeInTheDocument()
      expect(captured.body?.delivery_address).toMatchObject({
        latitude: 52.520008,
        longitude: 13.404954,
      })
    })

    it('leaves the coordinate keys out altogether when none is placed', async () => {
      const user = userEvent.setup()
      const captured = captureBody()
      renderScreen(<CheckoutScreen />, routeOptions)

      await fillAddress(user)
      await screen.findByTestId('map')
      await user.click(screen.getByRole('button', { name: 'Continue to payment' }))

      expect(await screen.findByTestId('payment-element')).toBeInTheDocument()
      expect(captured.body?.delivery_address).not.toHaveProperty('latitude')
      expect(captured.body?.delivery_address).not.toHaveProperty('longitude')
    })

    it('is not sent once it has been removed again', async () => {
      const user = userEvent.setup()
      const captured = captureBody()
      renderScreen(<CheckoutScreen />, routeOptions)

      await fillAddress(user)
      await screen.findByTestId('map')
      fireMapClick(52.5, 13.4)
      await user.click(screen.getByRole('button', { name: 'Remove pin' }))
      await user.click(screen.getByRole('button', { name: 'Continue to payment' }))

      expect(await screen.findByTestId('payment-element')).toBeInTheDocument()
      expect(captured.body?.delivery_address).not.toHaveProperty('latitude')
    })

    it('never blocks payment when the device refuses to share its location', async () => {
      const user = userEvent.setup()
      Object.defineProperty(navigator, 'geolocation', {
        configurable: true,
        value: { getCurrentPosition: (_ok: unknown, onError: () => void) => onError() },
      })
      stubCheckout()
      renderScreen(<CheckoutScreen />, routeOptions)

      await fillAddress(user)
      await user.click(await screen.findByRole('button', { name: 'Use my location' }))
      expect(screen.getByText(/Couldn't get your location/)).toBeInTheDocument()
      await user.click(screen.getByRole('button', { name: 'Continue to payment' }))

      expect(await screen.findByTestId('payment-element')).toBeInTheDocument()
    })
  })
})
