import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { stubAdminBackend } from '../../../test/mocks/adminBackend'
import { renderScreen } from '../../../test/test-utils'
import { CouriersScreen } from './CouriersScreen'

function renderCouriers(tab = 'couriers') {
  return renderScreen(<CouriersScreen />, {
    route: `/admin/couriers?tab=${tab}`,
    path: '/admin/couriers',
  })
}

describe('CouriersScreen', () => {
  it('lists couriers with their current load', async () => {
    stubAdminBackend()
    renderCouriers()

    const bekzod = (await screen.findByText('Bekzod')).closest('li')!
    expect(bekzod).toHaveTextContent('2 deliveries')
    expect(within(bekzod).getByRole('button', { name: 'Deactivate' })).toBeInTheDocument()
    const jasur = screen.getByText('Jasur').closest('li')!
    expect(within(jasur).getByRole('button', { name: 'Activate' })).toBeInTheDocument()
  })

  it('adds a courier', async () => {
    const backend = stubAdminBackend()
    renderCouriers()

    await userEvent.type(await screen.findByLabelText('Telegram ID'), '777')
    await userEvent.type(screen.getByLabelText('First name'), 'Otabek')
    await userEvent.click(screen.getByRole('button', { name: 'Add' }))

    await waitFor(() =>
      expect(backend.writes()[0]).toMatchObject({
        method: 'POST',
        path: '/couriers',
        body: { telegram_id: 777, name: 'Otabek', phone: null },
      }),
    )
  })

  it('deactivates a courier after confirming', async () => {
    const backend = stubAdminBackend()
    renderCouriers()

    const bekzod = (await screen.findByText('Bekzod')).closest('li')!
    await userEvent.click(within(bekzod).getByRole('button', { name: 'Deactivate' }))
    const dialog = await screen.findByRole('dialog')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Deactivate' }))

    await waitFor(() =>
      expect(backend.writes()[0]).toMatchObject({
        method: 'PATCH',
        path: '/couriers/3',
        body: { is_active: false },
      }),
    )
  })

  it('takes a delivery off its courier, warning harder once it is picked up', async () => {
    const backend = stubAdminBackend()
    renderCouriers('deliveries')

    const shipped = (await screen.findByRole('link', { name: 'Order #43' })).closest('li')!
    expect(shipped).toHaveTextContent('On the way')
    await userEvent.click(within(shipped).getByRole('button', { name: 'Take off courier' }))
    const dialog = await screen.findByRole('dialog')
    expect(dialog).toHaveTextContent('already picked this order up')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Take off courier' }))

    await waitFor(() =>
      expect(backend.writes()[0]).toMatchObject({ method: 'POST', path: '/shipments/6/release' }),
    )
  })

  it('shows working couriers on the map, stale ones marked', async () => {
    stubAdminBackend()
    renderCouriers('map')

    const marker = await screen.findByTestId('marker')
    expect(marker).toHaveAttribute('data-position', '41.31,69.24')
    expect(marker).toHaveAttribute('title', 'Bekzod')
    expect(screen.getByText('Position is old')).toBeInTheDocument()
  })

  it('switches tabs through the URL', async () => {
    stubAdminBackend()
    renderCouriers()
    await screen.findByText('Bekzod')

    await userEvent.click(screen.getByRole('tab', { name: 'Deliveries' }))

    expect(await screen.findByRole('link', { name: 'Order #42' })).toBeInTheDocument()
  })
})
