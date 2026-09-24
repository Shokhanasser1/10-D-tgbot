import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import {
  trackingAssigned,
  trackingDelivered,
  trackingProcessing,
  trackingShipped,
  trackingStale,
} from '../../../test/fixtures'
import { API } from '../../../test/mocks/handlers'
import { server } from '../../../test/mocks/server'
import { renderScreen } from '../../../test/test-utils'
import type { OrderStatus, Tracking } from '../types'
import { TrackingCard } from './TrackingCard'

const minutesAgo = (minutes: number) => new Date(Date.now() - minutes * 60_000).toISOString()

function stubTracking(tracking: Tracking) {
  server.use(http.get(`${API}/orders/:id/tracking`, () => HttpResponse.json(tracking)))
}

function renderCard(orderStatus: OrderStatus = 'paid') {
  return renderScreen(<TrackingCard orderId={5001} orderStatus={orderStatus} />)
}

function stepState(name: string) {
  const step = screen.getByText(name).closest('li')!
  return {
    current: step.getAttribute('aria-current') === 'step',
    done: step.className.includes('done'),
  }
}

describe('TrackingCard', () => {
  it('waits for a courier: first step reached, no courier, no map', async () => {
    stubTracking(trackingProcessing)
    renderCard()

    expect(await screen.findByText('Looking for a courier…')).toBeInTheDocument()
    expect(stepState('Payment received')).toEqual({ current: true, done: true })
    expect(stepState('Courier assigned').done).toBe(false)
    expect(screen.queryByTestId('map')).not.toBeInTheDocument()
  })

  it('treats an order with no shipment yet the same as one waiting for a courier', async () => {
    stubTracking({ ...trackingProcessing, status: null })
    renderCard()

    expect(await screen.findByText('Looking for a courier…')).toBeInTheDocument()
    expect(stepState('Payment received').current).toBe(true)
  })

  it('shows the delivery point at once when the customer dropped a pin', async () => {
    stubTracking({ ...trackingProcessing, destination: { latitude: 52.52, longitude: 13.405 } })
    renderCard()

    expect(await screen.findByTestId('map')).toBeInTheDocument()
    expect(screen.getAllByTestId('marker').map((m) => m.dataset.position)).toEqual(['52.52,13.405'])
  })

  it('names the courier once one is assigned, but shows no position', async () => {
    stubTracking(trackingAssigned)
    renderCard('processing')

    expect(await screen.findByText('Ali will pick up your order.')).toBeInTheDocument()
    expect(stepState('Courier assigned')).toEqual({ current: true, done: true })
    expect(stepState('Out for delivery').done).toBe(false)
    expect(screen.queryByTestId('map')).not.toBeInTheDocument()
  })

  it('follows the courier on a map while the order is out for delivery', async () => {
    stubTracking(trackingShipped)
    renderCard('shipped')

    expect(await screen.findByText('Ali is on the way.')).toBeInTheDocument()
    expect(stepState('Out for delivery')).toEqual({ current: true, done: true })
    expect(await screen.findByTestId('map')).toBeInTheDocument()
    expect(screen.getAllByTestId('marker').map((m) => m.dataset.position)).toEqual([
      '52.52,13.405',
      '52.5,13.4',
    ])
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('says it is waiting for the courier to share a location when none has arrived', async () => {
    stubTracking({ ...trackingShipped, courier_location: null })
    renderCard('shipped')

    expect(
      await screen.findByText('Ali is on the way. Waiting for their location…'),
    ).toBeInTheDocument()
    // Only the customer's own pin can be shown in the meantime.
    expect(screen.getAllByTestId('marker')).toHaveLength(1)
  })

  it('shows no map at all when there is neither a position nor a pin', async () => {
    stubTracking({ ...trackingShipped, courier_location: null, destination: null })
    renderCard('shipped')

    expect(await screen.findByText(/Waiting for their location/)).toBeInTheDocument()
    expect(screen.queryByTestId('map')).not.toBeInTheDocument()
  })

  it('warns when the courier position is stale, and says how old it is', async () => {
    stubTracking({
      ...trackingStale,
      courier_location: { ...trackingStale.courier_location!, updated_at: minutesAgo(5) },
    })
    renderCard('shipped')

    expect(await screen.findByRole('status')).toHaveTextContent(
      'Courier location updated 5 min ago',
    )
    // The last known position is still drawn, only marked as old.
    expect(await screen.findAllByTestId('marker')).toHaveLength(2)
  })

  it('never reports a negative age when the phone clock is behind the server', async () => {
    stubTracking({
      ...trackingStale,
      courier_location: {
        ...trackingStale.courier_location!,
        updated_at: new Date(Date.now() + 60_000).toISOString(),
      },
    })
    renderCard('shipped')

    expect(await screen.findByRole('status')).toHaveTextContent('updated 0 s ago')
  })

  it('completes the timeline and drops the map once delivered', async () => {
    stubTracking({ ...trackingDelivered, delivered_at: minutesAgo(3) })
    renderCard('delivered')

    expect(await screen.findByText('Delivered 3 min ago')).toBeInTheDocument()
    for (const step of [
      'Payment received',
      'Courier assigned',
      'Out for delivery',
      'Order delivered',
    ]) {
      expect(stepState(step).done).toBe(true)
    }
    expect(screen.queryByTestId('map')).not.toBeInTheDocument()
  })

  it('still says "delivered" when the time is unknown', async () => {
    stubTracking({ ...trackingDelivered, delivered_at: null })
    renderCard('delivered')

    expect(await screen.findByText('Your order has been delivered.')).toBeInTheDocument()
  })

  it.each<OrderStatus>(['pending_payment', 'cancelled'])(
    'shows nothing, and asks for nothing, for a %s order',
    async (status) => {
      let asked = false
      server.use(
        http.get(`${API}/orders/:id/tracking`, () => {
          asked = true
          return HttpResponse.json(trackingProcessing)
        }),
      )
      const { container } = renderCard(status)

      await new Promise((resolve) => setTimeout(resolve, 50))
      expect(asked).toBe(false)
      expect(container).toBeEmptyDOMElement()
    },
  )

  it('offers a retry, without an alarming error, when tracking fails to load', async () => {
    const user = userEvent.setup()
    let attempts = 0
    server.use(
      http.get(`${API}/orders/:id/tracking`, () => {
        attempts += 1
        return attempts === 1
          ? new HttpResponse(null, { status: 500 })
          : HttpResponse.json(trackingAssigned)
      }),
    )
    renderCard('processing')

    expect(await screen.findByText("Couldn't load delivery tracking.")).toBeInTheDocument()
    expect(screen.queryByText('Something went wrong')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Try again' }))

    expect(await screen.findByText('Ali will pick up your order.')).toBeInTheDocument()
  })
})
