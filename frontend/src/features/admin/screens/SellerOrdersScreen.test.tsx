import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { stubAdminBackend } from '../../../test/mocks/adminBackend'
import { renderScreen } from '../../../test/test-utils'
import { SellerOrderScreen, SellerOrdersScreen } from './SellerOrdersScreen'

describe('SellerOrdersScreen (Spec 10)', () => {
  it("lists the seller's orders, waiting ones first to catch the eye", async () => {
    stubAdminBackend('seller')
    renderScreen(<SellerOrdersScreen />, { route: '/admin/orders', path: '/admin/orders' })

    const waiting = await screen.findByRole('link', { name: /Order #42/ })
    expect(waiting).toHaveAttribute('href', '/admin/orders/42')
    expect(waiting).toHaveTextContent('Waiting for you')
    expect(waiting).toHaveTextContent('2 items')
    expect(waiting).toHaveTextContent('€29.98')
    expect(screen.getByRole('link', { name: /Order #40/ })).toHaveTextContent('Ready for pickup')
  })
})

describe('SellerOrderScreen (Spec 10)', () => {
  function renderOrder() {
    return renderScreen(<SellerOrderScreen />, {
      route: '/admin/orders/42',
      path: '/admin/orders/:orderId',
    })
  }

  it('lists the items and the goods total, and nothing about the customer', async () => {
    stubAdminBackend('seller')
    renderOrder()

    expect(await screen.findByRole('heading', { name: 'Order #42' })).toBeInTheDocument()
    expect(screen.getByText('Velvet Matte Lipstick')).toBeInTheDocument()
    expect(screen.getByText(/LIP-VELVET-RED · 2 × €14\.99/)).toBeInTheDocument()
    expect(screen.getByText('€29.98')).toBeInTheDocument()
    expect(screen.queryByText(/Aziza|Amir Temur|\+998/)).not.toBeInTheDocument()
  })

  it('tells the platform the order is ready for pickup', async () => {
    const backend = stubAdminBackend('seller')
    renderOrder()

    await userEvent.click(await screen.findByRole('button', { name: 'Ready for pickup' }))

    await waitFor(() =>
      expect(backend.writes()[0]).toMatchObject({ method: 'POST', path: '/orders/42/ready' }),
    )
  })
})
