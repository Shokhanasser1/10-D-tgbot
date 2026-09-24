import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { orderDetail } from '../../../test/fixtures'
import { API } from '../../../test/mocks/handlers'
import { server } from '../../../test/mocks/server'
import { renderScreen } from '../../../test/test-utils'
import { OrderDetailScreen } from './OrderDetailScreen'
import { OrdersListScreen } from './OrdersListScreen'

describe('OrdersListScreen', () => {
  const listOptions = {
    route: '/orders',
    path: '/orders',
    extraRoutes: [{ path: '/orders/:orderId', element: <div>order page</div> }],
  }

  it('lists orders with their translated status', async () => {
    renderScreen(<OrdersListScreen />, listOptions)

    expect(await screen.findByText('#5001')).toBeInTheDocument()
    expect(screen.getByText('Paid')).toBeInTheDocument()
    expect(screen.getByText('Awaiting payment')).toBeInTheDocument()
  })

  it('opens an order when it is tapped', async () => {
    const user = userEvent.setup()
    renderScreen(<OrdersListScreen />, listOptions)

    await user.click(await screen.findByText('#5001'))

    expect(await screen.findByText('order page')).toBeInTheDocument()
  })

  it('shows the empty state when there are no orders', async () => {
    server.use(http.get(`${API}/orders`, () => HttpResponse.json([])))
    renderScreen(<OrdersListScreen />, listOptions)

    expect(await screen.findByText('No orders yet')).toBeInTheDocument()
  })

  it('shows an error, not the empty state, when loading fails', async () => {
    server.use(http.get(`${API}/orders`, () => new HttpResponse(null, { status: 500 })))
    renderScreen(<OrdersListScreen />, listOptions)

    expect(await screen.findByText('Something went wrong')).toBeInTheDocument()
    expect(screen.queryByText('No orders yet')).not.toBeInTheDocument()
  })
})

describe('OrderDetailScreen', () => {
  const detailOptions = { route: '/orders/5001', path: '/orders/:orderId' }

  it('shows the items, delivery address and status', async () => {
    renderScreen(<OrderDetailScreen />, detailOptions)

    expect(await screen.findByText('#5001')).toBeInTheDocument()
    expect(screen.getByText('Paid')).toBeInTheDocument()
    expect(screen.getByText(/Velvet Matte Lipstick × 2/)).toBeInTheDocument()
    expect(screen.getByText(/Alexanderplatz 1, Berlin 10178, DE/)).toBeInTheDocument()
    expect(screen.getByText('+491234567')).toBeInTheDocument()
  })

  it('shows the delivery notes only when there are some', async () => {
    server.use(
      http.get(`${API}/orders/:id`, () =>
        HttpResponse.json({
          ...orderDetail,
          delivery_address: { ...orderDetail.delivery_address, notes: 'Leave at the door' },
        }),
      ),
    )
    renderScreen(<OrderDetailScreen />, detailOptions)

    expect(await screen.findByText('Leave at the door')).toBeInTheDocument()
  })

  it('shows an error with retry when the order is not found', async () => {
    server.use(http.get(`${API}/orders/:id`, () => new HttpResponse(null, { status: 404 })))
    renderScreen(<OrderDetailScreen />, detailOptions)

    expect(await screen.findByText('Something went wrong')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
  })
})
