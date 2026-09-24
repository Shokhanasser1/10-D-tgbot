import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { orderDetail, trackingAssigned } from '../../../test/fixtures'
import { API } from '../../../test/mocks/handlers'
import { server } from '../../../test/mocks/server'
import { renderScreen } from '../../../test/test-utils'
import { OrderDetailScreen } from './OrderDetailScreen'

const detailOptions = { route: '/orders/5001', path: '/orders/:orderId' }

describe('OrderDetailScreen tracking', () => {
  it('shows the delivery progress above the order contents', async () => {
    server.use(http.get(`${API}/orders/:id/tracking`, () => HttpResponse.json(trackingAssigned)))
    renderScreen(<OrderDetailScreen />, detailOptions)

    expect(await screen.findByText('Ali will pick up your order.')).toBeInTheDocument()
    expect(screen.getByText(/Velvet Matte Lipstick × 2/)).toBeInTheDocument()
  })

  // Tracking is a bonus on this page: without it the order is still fully readable.
  it('keeps the rest of the order when tracking fails', async () => {
    server.use(
      http.get(`${API}/orders/:id/tracking`, () => new HttpResponse(null, { status: 500 })),
    )
    renderScreen(<OrderDetailScreen />, detailOptions)

    expect(await screen.findByText("Couldn't load delivery tracking.")).toBeInTheDocument()
    expect(screen.getByText('#5001')).toBeInTheDocument()
    expect(screen.getByText(/Velvet Matte Lipstick × 2/)).toBeInTheDocument()
    expect(screen.getByText(/Alexanderplatz 1, Berlin 10178, DE/)).toBeInTheDocument()
    expect(screen.queryByText('Something went wrong')).not.toBeInTheDocument()
  })

  it('does not track an order that has not been paid', async () => {
    let asked = false
    server.use(
      http.get(`${API}/orders/:id`, () =>
        HttpResponse.json({ ...orderDetail, status: 'pending_payment', shipment_status: null }),
      ),
      http.get(`${API}/orders/:id/tracking`, () => {
        asked = true
        return HttpResponse.json(trackingAssigned)
      }),
    )
    renderScreen(<OrderDetailScreen />, detailOptions)

    expect(await screen.findByText('Awaiting payment')).toBeInTheDocument()
    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(asked).toBe(false)
    expect(screen.queryByText('Payment received')).not.toBeInTheDocument()
  })
})
