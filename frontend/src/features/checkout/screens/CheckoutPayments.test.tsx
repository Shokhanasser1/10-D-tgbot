import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { API } from '../../../test/mocks/handlers'
import { server } from '../../../test/mocks/server'
import { renderScreen } from '../../../test/test-utils'
import { CheckoutScreen } from './CheckoutScreen'

vi.mock('@stripe/stripe-js', () => ({ loadStripe: vi.fn(() => Promise.resolve({})) }))

const routeOptions = {
  route: '/checkout',
  path: '/checkout',
  extraRoutes: [{ path: '/orders/:orderId', element: <div>order page</div> }],
}

async function fillAddress(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByPlaceholderText('Street address'), 'Amir Temur 1')
  await user.type(screen.getByPlaceholderText('City'), 'Tashkent')
  await user.type(screen.getByPlaceholderText('Postal code'), '100000')
  await user.type(screen.getByPlaceholderText('Country'), 'UZ')
  await user.type(screen.getByPlaceholderText('Phone'), '+998901234567')
}

function offer(methods: string[]) {
  server.use(
    http.get(`${API}/checkout/methods`, () => HttpResponse.json({ methods, currency: 'UZS' })),
  )
}

function stubCheckout(response: Record<string, unknown>, onBody?: (body: unknown) => void) {
  server.use(
    http.post(`${API}/checkout`, async ({ request }) => {
      onBody?.(await request.json())
      return HttpResponse.json({
        order_id: 88,
        total: '198000.00',
        currency: 'UZS',
        reserved_until: '2026-09-29T10:15:00Z',
        client_secret: null,
        invoice_url: null,
        ...response,
      })
    }),
  )
}

function stubTelegram(openInvoice: (url: string, cb: (status: string) => void) => void) {
  window.Telegram = {
    WebApp: { initData: 'query_id=1&hash=x', initDataUnsafe: {}, openInvoice },
  } as unknown as Window['Telegram']
}

afterEach(() => {
  delete window.Telegram
})

describe('CheckoutScreen payment methods', () => {
  it('offers the shop methods and hides the choice when there is only one', async () => {
    offer(['stripe'])
    renderScreen(<CheckoutScreen />, routeOptions)
    await screen.findByRole('button', { name: 'Continue to payment' })
    expect(screen.queryByText('Payment')).not.toBeInTheDocument()
  })

  it('places a cash order and goes straight to it', async () => {
    const user = userEvent.setup()
    offer(['telegram', 'cash'])
    let body: unknown = null
    stubCheckout({ payment_method: 'cash' }, (received) => {
      body = received
    })
    renderScreen(<CheckoutScreen />, routeOptions)

    await user.click(await screen.findByLabelText(/Cash on delivery/))
    await fillAddress(user)
    await user.click(screen.getByRole('button', { name: 'Place order' }))

    expect(await screen.findByText('order page')).toBeInTheDocument()
    expect(body).toMatchObject({ payment_method: 'cash' })
  })

  it('opens the Telegram invoice and lands on the order once paid', async () => {
    const user = userEvent.setup()
    offer(['telegram', 'cash'])
    stubCheckout({ payment_method: 'telegram', invoice_url: 'https://t.me/$inv' })
    const openInvoice = vi.fn((_url: string, cb: (status: string) => void) => cb('paid'))
    stubTelegram(openInvoice)
    renderScreen(<CheckoutScreen />, routeOptions)

    await fillAddress(user)
    await user.click(await screen.findByRole('button', { name: 'Continue to payment' }))

    expect(await screen.findByText('order page')).toBeInTheDocument()
    expect(openInvoice).toHaveBeenCalledWith('https://t.me/$inv', expect.any(Function))
  })

  it('lets the customer reopen an invoice they closed', async () => {
    const user = userEvent.setup()
    offer(['telegram'])
    stubCheckout({ payment_method: 'telegram', invoice_url: 'https://t.me/$inv' })
    const answers = ['cancelled', 'paid']
    const openInvoice = vi.fn((_url: string, cb: (status: string) => void) =>
      cb(answers.shift() ?? 'paid'),
    )
    stubTelegram(openInvoice)
    renderScreen(<CheckoutScreen />, routeOptions)

    await fillAddress(user)
    await user.click(await screen.findByRole('button', { name: 'Continue to payment' }))
    expect(await screen.findByText(/Payment was not completed/)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Pay' }))

    expect(await screen.findByText('order page')).toBeInTheDocument()
    expect(openInvoice).toHaveBeenCalledTimes(2)
  })

  it('says so instead of failing when the shop has no payment method yet', async () => {
    offer([])
    renderScreen(<CheckoutScreen />, routeOptions)

    expect(await screen.findByText('Payments are not set up in this shop yet.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Continue to payment' })).toBeDisabled()
  })
})
