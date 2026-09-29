import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { adminOrder } from '../../../test/adminFixtures'
import { stubAdminBackend } from '../../../test/mocks/adminBackend'
import { API } from '../../../test/mocks/handlers'
import { server } from '../../../test/mocks/server'
import { renderScreen } from '../../../test/test-utils'
import { OrderDetailScreen } from './OrderDetailScreen'

function renderOrder(id = 42) {
  return renderScreen(<OrderDetailScreen />, {
    route: `/admin/orders/${id}`,
    path: '/admin/orders/:orderId',
  })
}

function serve(order: ReturnType<typeof adminOrder>) {
  server.use(http.get(`${API}/internal/orders/:id`, () => HttpResponse.json(order)))
}

describe('OrderDetailScreen', () => {
  it('shows items, totals, customer contact, address and the pin', async () => {
    stubAdminBackend()
    renderOrder()

    expect(await screen.findByRole('heading', { name: 'Order #42' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Velvet Matte Lipstick' })).toHaveAttribute(
      'href',
      '/admin/catalog/products/1',
    )
    expect(screen.getByText('LIP-VELVET-RED · 2 × €14.99')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '+998901112233' })).toHaveAttribute(
      'href',
      'tel:+998901112233',
    )
    expect(screen.getByText('Call first')).toBeInTheDocument()
    expect(screen.getByText('No courier yet')).toBeInTheDocument()
    expect(await screen.findByTestId('marker')).toHaveAttribute('data-position', '41.3,69.2')
  })

  it('cancels only with a reason, and shows the refund under way', async () => {
    const backend = stubAdminBackend()
    renderOrder()

    await userEvent.click(await screen.findByRole('button', { name: 'Cancel and refund' }))
    const dialog = await screen.findByRole('dialog')
    const confirm = within(dialog).getByRole('button', { name: 'Cancel order' })
    expect(within(dialog).getByText(/gets €34.97 back in full/)).toBeInTheDocument()
    expect(confirm).toBeDisabled()

    await userEvent.type(within(dialog).getByLabelText(/Reason/), '  Customer asked  ')
    await userEvent.click(confirm)

    await waitFor(() =>
      expect(backend.writes()[0]).toMatchObject({
        method: 'POST',
        path: '/orders/42/cancel',
        body: { reason: 'Customer asked' },
      }),
    )
    expect(await screen.findByText('Refund in progress')).toBeInTheDocument()
  })

  it('explains that the courier got there first', async () => {
    stubAdminBackend()
    server.use(
      http.post(`${API}/internal/orders/:id/cancel`, () =>
        HttpResponse.json({ detail: 'x', code: 'invalid_state' }, { status: 409 }),
      ),
    )
    renderOrder()

    await userEvent.click(await screen.findByRole('button', { name: 'Cancel and refund' }))
    const dialog = await screen.findByRole('dialog')
    await userEvent.type(within(dialog).getByLabelText(/Reason/), 'x')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Cancel order' }))

    expect(await within(dialog).findByRole('alert')).toHaveTextContent(
      'the order or delivery has moved on',
    )
  })

  it('cannot cancel once the courier has picked up', async () => {
    stubAdminBackend()
    serve(
      adminOrder({
        status: 'shipped',
        can_cancel: false,
        shipment: {
          id: 5,
          status: 'shipped',
          courier_id: 3,
          courier_name: 'Bekzod',
          assigned_at: '2026-09-24T11:00:00Z',
          picked_up_at: '2026-09-24T11:30:00Z',
          delivered_at: null,
        },
      }),
    )
    renderOrder()

    expect(await screen.findByText('Courier: Bekzod')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Cancel and refund' })).not.toBeInTheDocument()
    expect(screen.getByText(/already picked this order up/)).toBeInTheDocument()
    expect(screen.getByText('Picked up')).toBeInTheDocument()
  })

  it('retries a failed refund', async () => {
    const backend = stubAdminBackend()
    serve(
      adminOrder({
        status: 'cancelled',
        can_cancel: false,
        cancel_reason: 'Out of stock',
        cancelled_at: '2026-09-24T12:00:00Z',
        payment: { status: 'succeeded', amount: '34.97', refund_status: 'failed' },
      }),
    )
    renderOrder()

    expect(await screen.findByText('Cancelled: Out of stock')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Retry refund' }))

    await waitFor(() =>
      expect(backend.writes()[0]).toMatchObject({ method: 'POST', path: '/orders/42/refund' }),
    )
  })

  it('translates the reason of an order the system cancelled', async () => {
    stubAdminBackend()
    serve(
      adminOrder({
        status: 'cancelled',
        can_cancel: false,
        cancel_reason: 'payment_expired',
        cancelled_at: '2026-09-24T12:00:00Z',
      }),
    )
    renderOrder()

    expect(await screen.findByText('Cancelled: not paid in time')).toBeInTheDocument()
  })

  it('asks an owner to refund a Click/Payme payment by hand and to confirm it', async () => {
    const backend = stubAdminBackend()
    serve(
      adminOrder({
        status: 'cancelled',
        can_cancel: false,
        cancel_reason: 'Broken',
        cancelled_at: '2026-09-24T12:00:00Z',
        payment: {
          method: 'telegram',
          status: 'succeeded',
          amount: '34.97',
          refund_status: 'manual_required',
          telegram_payment_charge_id: 'tg_1',
          provider_payment_charge_id: 'click_777',
        },
      }),
    )
    renderOrder()

    expect(
      await screen.findByText(/Click\/Payme cabinet\. Payment ID: click_777/),
    ).toBeInTheDocument()
    expect(screen.getByText('Payment: Click/Payme')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Refund done' }))

    await waitFor(() =>
      expect(backend.writes()[0]).toMatchObject({
        method: 'POST',
        path: '/orders/42/refund/confirm',
      }),
    )
  })
})
