import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { formatClock } from '../../../shared/time/formatClock'
import { orderDetail } from '../../../test/fixtures'
import { renderScreen } from '../../../test/test-utils'
import type { OrderDetail } from '../types'
import { PaymentNotice } from './PaymentNotice'

function renderNotice(overrides: Partial<OrderDetail>) {
  return renderScreen(<PaymentNotice order={{ ...orderDetail, ...overrides }} />, {
    extraRoutes: [{ path: '/cart', element: <div>cart page</div> }],
  })
}

describe('PaymentNotice', () => {
  it('shows the payment deadline of an unpaid order', () => {
    renderNotice({ status: 'pending_payment', reserved_until: '2026-09-22T10:15:00Z' })

    const time = formatClock('2026-09-22T10:15:00Z', 'en')
    expect(screen.getByText(new RegExp(`We hold your items until ${time}`))).toBeInTheDocument()
  })

  it('says the items are back in the cart after the order expired, with a way there', async () => {
    const user = userEvent.setup()
    renderNotice({ status: 'cancelled', cancel_reason: 'payment_expired' })

    expect(
      screen.getByText('Payment time ran out. Your items are back in the cart.'),
    ).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Open cart' }))
    expect(await screen.findByText('cart page')).toBeInTheDocument()
  })

  it('shows a refund of a payment that arrived too late', () => {
    renderNotice({
      status: 'cancelled',
      cancel_reason: 'payment_expired',
      refund_status: 'pending',
    })

    expect(screen.getByText('Your payment is being refunded.')).toBeInTheDocument()
  })

  it('shows a refund of an order the shop cancelled, without the cart button', () => {
    renderNotice({ status: 'cancelled', cancel_reason: 'Out of stock', refund_status: 'succeeded' })

    expect(screen.getByText('Your payment has been refunded.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Open cart' })).not.toBeInTheDocument()
  })

  it('renders nothing for a normal paid order', () => {
    const { container } = renderNotice({})

    expect(container).toBeEmptyDOMElement()
  })

  it('reminds a cash customer what to pay on delivery', () => {
    renderNotice({
      payment_method: 'cash',
      status: 'paid',
      payment_status: 'requires_payment_method',
      total: '198000.00',
      currency: 'UZS',
    })

    expect(screen.getByText(/^Pay in cash on delivery: UZS.198,000$/)).toBeInTheDocument()
  })

  it('says the shop is refunding a Click/Payme payment by hand', () => {
    renderNotice({ status: 'cancelled', refund_status: 'manual_required' })

    expect(screen.getByText('The shop is refunding your payment.')).toBeInTheDocument()
  })
})
