import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { assignedDelivery, poolItems, shippedDelivery } from '../../../test/fixtures'
import { API } from '../../../test/mocks/handlers'
import { stubCourierBackend } from '../../../test/mocks/courierBackend'
import { server } from '../../../test/mocks/server'
import { renderScreen } from '../../../test/test-utils'
import { CourierScreen } from './CourierScreen'

const poolRoute = {
  route: '/courier',
  path: '/courier',
  extraRoutes: [{ path: '/', element: <div>storefront home</div> }],
}
const mineRoute = { ...poolRoute, route: '/courier?tab=mine' }

function stubOpenLink() {
  const openLink = vi.fn()
  const openTelegramLink = vi.fn()
  window.Telegram = {
    WebApp: { initData: 'x', openLink, openTelegramLink },
  } as unknown as Window['Telegram']
  return { openLink, openTelegramLink }
}

afterEach(() => {
  delete window.Telegram
})

describe('CourierScreen: access', () => {
  it('sends a customer, who is not a courier, back to the storefront', async () => {
    // The default handler answers /courier/me with 403, as it does for every customer.
    renderScreen(<CourierScreen />, poolRoute)

    expect(await screen.findByText('storefront home')).toBeInTheDocument()
    expect(screen.queryByText('Courier')).not.toBeInTheDocument()
  })

  it('does not even ask for the pool when the user is not a courier', async () => {
    let asked = false
    server.use(
      http.get(`${API}/courier/pool`, () => {
        asked = true
        return HttpResponse.json([])
      }),
    )
    renderScreen(<CourierScreen />, poolRoute)

    await screen.findByText('storefront home')
    expect(asked).toBe(false)
  })

  it('leaves when the courier is deactivated while the app is open', async () => {
    stubCourierBackend()
    server.use(
      http.get(`${API}/courier/pool`, () =>
        HttpResponse.json({ detail: 'Not a courier' }, { status: 403 }),
      ),
    )
    renderScreen(<CourierScreen />, poolRoute)

    expect(await screen.findByText('storefront home')).toBeInTheDocument()
  })

  it('shows an error, not a redirect, when the profile cannot be loaded', async () => {
    server.use(http.get(`${API}/courier/me`, () => new HttpResponse(null, { status: 500 })))
    renderScreen(<CourierScreen />, poolRoute)

    expect(await screen.findByText('Something went wrong')).toBeInTheDocument()
    expect(screen.queryByText('storefront home')).not.toBeInTheDocument()
  })
})

describe('CourierScreen: pool', () => {
  it('lists waiting orders with just enough to decide, and no customer details', async () => {
    stubCourierBackend()
    renderScreen(<CourierScreen />, poolRoute)

    expect(await screen.findByText('#41')).toBeInTheDocument()
    expect(screen.getByText('Alexanderplatz 1, Berlin')).toBeInTheDocument()
    expect(screen.getByText('2 items')).toBeInTheDocument()
    expect(screen.getByText('1 item')).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'Take this order' })).toHaveLength(2)
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
  })

  it('shows how many active deliveries the courier holds out of the limit', async () => {
    stubCourierBackend({ deliveries: [assignedDelivery] })
    renderScreen(<CourierScreen />, poolRoute)

    expect(await screen.findByText('1 of 3 active deliveries')).toBeInTheDocument()
  })

  it('shows an empty state when nothing is waiting', async () => {
    stubCourierBackend({ pool: [] })
    renderScreen(<CourierScreen />, poolRoute)

    expect(await screen.findByText('No orders waiting')).toBeInTheDocument()
  })

  it('shows an error, not the empty state, when the pool cannot be loaded', async () => {
    stubCourierBackend()
    server.use(http.get(`${API}/courier/pool`, () => new HttpResponse(null, { status: 500 })))
    renderScreen(<CourierScreen />, poolRoute)

    expect(await screen.findByText('Something went wrong')).toBeInTheDocument()
    expect(screen.queryByText('No orders waiting')).not.toBeInTheDocument()
  })

  it('claims an order, which then moves to My deliveries', async () => {
    const user = userEvent.setup()
    const backend = stubCourierBackend()
    renderScreen(<CourierScreen />, poolRoute)
    await screen.findByText('#41')

    await user.click(screen.getAllByRole('button', { name: 'Take this order' })[0])

    expect(backend.actions).toEqual([{ step: 'claim', shipmentId: 501 }])
    await vi.waitFor(() => expect(screen.queryByText('#41')).not.toBeInTheDocument())
    expect(screen.getByText('#42')).toBeInTheDocument()

    await user.click(screen.getByRole('tab', { name: /My deliveries/ }))
    expect(await screen.findByText('#41')).toBeInTheDocument()
    expect(screen.getByText('Pick up at the shop')).toBeInTheDocument()
  })

  it('shows the count of orders and of my deliveries on the tabs', async () => {
    stubCourierBackend({ deliveries: [assignedDelivery] })
    renderScreen(<CourierScreen />, poolRoute)

    const availableTab = await screen.findByRole('tab', { name: /Available/ })
    await vi.waitFor(() => expect(within(availableTab).getByText('2')).toBeInTheDocument())
    expect(within(screen.getByRole('tab', { name: /My deliveries/ })).getByText('1')).toBeVisible()
  })

  it('explains, and refreshes the pool, when another courier was faster', async () => {
    const user = userEvent.setup()
    const backend = stubCourierBackend()
    server.use(
      http.post(`${API}/courier/deliveries/:id/claim`, () => {
        // The other courier's claim is what makes the order disappear from the pool.
        backend.pool = backend.pool.filter((item) => item.shipment_id !== 501)
        return HttpResponse.json(
          { detail: 'Already taken', code: 'shipment_taken' },
          { status: 409 },
        )
      }),
    )
    renderScreen(<CourierScreen />, poolRoute)
    await screen.findByText('#41')

    await user.click(screen.getAllByRole('button', { name: 'Take this order' })[0])

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Another courier just took this order.',
    )
    await vi.waitFor(() => expect(screen.queryByText('#41')).not.toBeInTheDocument())
    expect(screen.getByText('#42')).toBeInTheDocument()
  })

  it('explains the delivery limit', async () => {
    const user = userEvent.setup()
    stubCourierBackend()
    server.use(
      http.post(`${API}/courier/deliveries/:id/claim`, () =>
        HttpResponse.json({ detail: 'Limit', code: 'delivery_limit_reached' }, { status: 409 }),
      ),
    )
    renderScreen(<CourierScreen />, poolRoute)

    await user.click((await screen.findAllByRole('button', { name: 'Take this order' }))[0])

    expect(await screen.findByRole('alert')).toHaveTextContent(/limit of active deliveries/)
  })

  it('clears the previous message when the next action starts', async () => {
    const user = userEvent.setup()
    stubCourierBackend()
    let failed = false
    server.use(
      http.post(`${API}/courier/deliveries/:id/claim`, () => {
        if (!failed) {
          failed = true
          return HttpResponse.json({ detail: 'x', code: 'shipment_taken' }, { status: 409 })
        }
        return HttpResponse.json({ shipment_id: 502, order_id: 42, status: 'assigned' })
      }),
    )
    renderScreen(<CourierScreen />, poolRoute)

    await user.click((await screen.findAllByRole('button', { name: 'Take this order' }))[0])
    await screen.findByRole('alert')
    await user.click(screen.getAllByRole('button', { name: 'Take this order' })[0])

    await vi.waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument())
  })

  it('falls back to a generic message for an unexpected failure', async () => {
    const user = userEvent.setup()
    stubCourierBackend()
    server.use(
      http.post(
        `${API}/courier/deliveries/:id/claim`,
        () => new HttpResponse(null, { status: 500 }),
      ),
    )
    renderScreen(<CourierScreen />, poolRoute)

    await user.click((await screen.findAllByRole('button', { name: 'Take this order' }))[0])

    expect(await screen.findByRole('alert')).toHaveTextContent('Something went wrong')
  })
})

describe('CourierScreen: my deliveries', () => {
  it('shows everything the courier needs at the door', async () => {
    stubCourierBackend({ deliveries: [assignedDelivery] })
    renderScreen(<CourierScreen />, mineRoute)

    expect(await screen.findByText('#41')).toBeInTheDocument()
    expect(screen.getByText(/Alexanderplatz 1, Berlin 10178, DE/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '+49 123 4567' })).toHaveAttribute(
      'href',
      'tel:+491234567',
    )
    expect(screen.getByText('Ring twice')).toBeInTheDocument()
    expect(screen.getByText('Velvet Matte Lipstick × 2')).toBeInTheDocument()
  })

  it('opens a map at the pin the customer dropped', async () => {
    const user = userEvent.setup()
    const { openLink } = stubOpenLink()
    stubCourierBackend({ deliveries: [assignedDelivery] })
    renderScreen(<CourierScreen />, mineRoute)

    await user.click(await screen.findByRole('button', { name: 'Open in maps' }))

    expect(openLink).toHaveBeenCalledWith(
      'https://www.google.com/maps/search/?api=1&query=52.52%2C13.405',
    )
  })

  it('falls back to the typed address for a map when there is no pin', async () => {
    const user = userEvent.setup()
    const { openLink } = stubOpenLink()
    stubCourierBackend({ deliveries: [shippedDelivery] })
    renderScreen(<CourierScreen />, mineRoute)

    await user.click(await screen.findByRole('button', { name: 'Open in maps' }))

    const url = new URL(openLink.mock.calls[0][0] as string)
    expect(url.searchParams.get('query')).toBe('Kastanienallee 5, Berlin, 10178, DE')
  })

  it('offers pick-up and give-back before pick-up, and only delivery after it', async () => {
    stubCourierBackend({ deliveries: [assignedDelivery, shippedDelivery] })
    renderScreen(<CourierScreen />, mineRoute)

    const assigned = (await screen.findByText('#41')).closest('div')!.parentElement!
    const shipped = screen.getByText('#42').closest('div')!.parentElement!

    expect(within(assigned).getByRole('button', { name: 'Picked up' })).toBeInTheDocument()
    expect(within(assigned).getByRole('button', { name: 'Give back' })).toBeInTheDocument()
    expect(within(assigned).queryByRole('button', { name: 'Delivered' })).not.toBeInTheDocument()

    expect(within(shipped).getByRole('button', { name: 'Delivered' })).toBeInTheDocument()
    expect(within(shipped).queryByRole('button', { name: 'Give back' })).not.toBeInTheDocument()
    expect(within(shipped).queryByRole('button', { name: 'Picked up' })).not.toBeInTheDocument()
  })

  it('walks a delivery through pick-up and delivery', async () => {
    const user = userEvent.setup()
    const backend = stubCourierBackend({ deliveries: [assignedDelivery] })
    renderScreen(<CourierScreen />, mineRoute)

    await user.click(await screen.findByRole('button', { name: 'Picked up' }))
    await user.click(await screen.findByRole('button', { name: 'Delivered' }))

    expect(backend.actions).toEqual([
      { step: 'pickup', shipmentId: 501 },
      { step: 'deliver', shipmentId: 501 },
    ])
    expect(await screen.findByText('No active deliveries')).toBeInTheDocument()
  })

  it('gives an order back to the pool', async () => {
    const user = userEvent.setup()
    const backend = stubCourierBackend({ pool: [], deliveries: [assignedDelivery] })
    renderScreen(<CourierScreen />, mineRoute)

    await user.click(await screen.findByRole('button', { name: 'Give back' }))

    expect(backend.actions).toEqual([{ step: 'release', shipmentId: 501 }])
    expect(await screen.findByText('No active deliveries')).toBeInTheDocument()
    await user.click(screen.getByRole('tab', { name: /Available/ }))
    expect(await screen.findByText('#41')).toBeInTheDocument()
  })

  it('only disables the card an action is running for', async () => {
    const user = userEvent.setup()
    stubCourierBackend({ deliveries: [assignedDelivery, shippedDelivery] })
    server.use(
      http.post(`${API}/courier/deliveries/:id/pickup`, async () => {
        await new Promise((resolve) => setTimeout(resolve, 150))
        return HttpResponse.json({ shipment_id: 501, order_id: 41, status: 'shipped' })
      }),
    )
    renderScreen(<CourierScreen />, mineRoute)

    await user.click(await screen.findByRole('button', { name: 'Picked up' }))

    expect(screen.getByRole('button', { name: 'Give back' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Delivered' })).toBeEnabled()
    await vi.waitFor(() => expect(screen.getByRole('button', { name: 'Give back' })).toBeEnabled())
  })

  it('reports a delivery that changed underneath the courier', async () => {
    const user = userEvent.setup()
    stubCourierBackend({ deliveries: [shippedDelivery] })
    server.use(
      http.post(`${API}/courier/deliveries/:id/deliver`, () =>
        HttpResponse.json({ detail: 'x', code: 'invalid_state' }, { status: 409 }),
      ),
    )
    renderScreen(<CourierScreen />, mineRoute)

    await user.click(await screen.findByRole('button', { name: 'Delivered' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('This delivery has changed')
  })

  it('shows an empty state without the GPS panel when nothing is held', async () => {
    stubCourierBackend()
    renderScreen(<CourierScreen />, mineRoute)

    expect(await screen.findByText('No active deliveries')).toBeInTheDocument()
    expect(screen.queryByText('Share your live location')).not.toBeInTheDocument()
  })
})

describe('CourierScreen: GPS panel', () => {
  it('explains how to share a live location and says nothing has arrived yet', async () => {
    stubCourierBackend({ deliveries: [assignedDelivery] })
    renderScreen(<CourierScreen />, mineRoute)

    expect(await screen.findByText('Share your live location')).toBeInTheDocument()
    expect(screen.getByText(/Share Live Location/)).toBeInTheDocument()
    expect(screen.getByText('No GPS updates yet')).toBeInTheDocument()
  })

  it('shows how fresh the last position is', async () => {
    const fiveSecondsAgo = new Date(Date.now() - 5_000).toISOString()
    stubCourierBackend({ deliveries: [assignedDelivery], locationUpdatedAt: fiveSecondsAgo })
    renderScreen(<CourierScreen />, mineRoute)

    expect(await screen.findByText(/GPS updated \d+ s ago/)).toBeInTheDocument()
    expect(screen.queryByText('No GPS updates yet')).not.toBeInTheDocument()
  })

  it('opens the bot chat', async () => {
    const user = userEvent.setup()
    const { openTelegramLink } = stubOpenLink()
    stubCourierBackend({ deliveries: [assignedDelivery] })
    renderScreen(<CourierScreen />, mineRoute)

    await user.click(await screen.findByRole('button', { name: 'Open bot chat' }))

    expect(openTelegramLink).toHaveBeenCalledWith('https://t.me/shop_courier_bot')
  })

  it('has no bot button when the bot username is not configured', async () => {
    stubCourierBackend({ deliveries: [assignedDelivery], botUsername: null })
    renderScreen(<CourierScreen />, mineRoute)

    await screen.findByText('Share your live location')
    expect(screen.queryByRole('button', { name: 'Open bot chat' })).not.toBeInTheDocument()
  })
})

describe('CourierScreen: tabs', () => {
  it('opens on the pool by default and remembers the tab in the URL', async () => {
    const user = userEvent.setup()
    stubCourierBackend({ deliveries: [assignedDelivery] })
    renderScreen(<CourierScreen />, poolRoute)

    expect(await screen.findByRole('tab', { name: /Available/ })).toHaveAttribute(
      'aria-selected',
      'true',
    )
    await user.click(screen.getByRole('tab', { name: /My deliveries/ }))

    expect(screen.getByRole('tab', { name: /My deliveries/ })).toHaveAttribute(
      'aria-selected',
      'true',
    )
    expect(await screen.findByText('Pick up at the shop')).toBeInTheDocument()
  })

  it('opens on My deliveries when the URL says so', async () => {
    stubCourierBackend({ deliveries: [assignedDelivery] })
    renderScreen(<CourierScreen />, mineRoute)

    expect(await screen.findByText('Pick up at the shop')).toBeInTheDocument()
    expect(screen.queryByText(poolItems[1].street, { exact: false })).not.toBeInTheDocument()
  })
})
