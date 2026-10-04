import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { adminMe } from '../../../test/adminFixtures'
import { stubAdminBackend } from '../../../test/mocks/adminBackend'
import { renderScreen } from '../../../test/test-utils'
import { AdminMeProvider } from '../meContext'
import { SellersScreen } from './SellersScreen'

function renderSellers() {
  return renderScreen(<SellersScreen />, { route: '/admin/sellers', path: '/admin/sellers' })
}

describe('SellersScreen', () => {
  it('lists sellers with their address, products, account and status', async () => {
    stubAdminBackend()
    renderSellers()

    const lola = (await screen.findByText('Lola Beauty')).closest('li')!
    expect(lola).toHaveTextContent('Tashkent, Chilonzor 5')
    expect(lola).toHaveTextContent('1 product')
    expect(lola).toHaveTextContent('Lola · 502')
    expect(within(lola).getByRole('button', { name: 'Deactivate' })).toBeInTheDocument()

    const anor = screen.getByText('Anor').closest('li')!
    expect(anor).toHaveTextContent('Deactivated')
    expect(within(anor).getByRole('button', { name: 'Activate' })).toBeInTheDocument()
  })

  it('adds a seller together with its account', async () => {
    const backend = stubAdminBackend()
    renderSellers()

    await userEvent.type(await screen.findByLabelText('Shop name'), ' Zara Cosmetics ')
    await userEvent.type(screen.getByLabelText('Phone'), '+998900000000')
    await userEvent.type(screen.getByLabelText('Pickup address'), 'Tashkent, Yunusobod 4')
    await userEvent.type(screen.getByLabelText('Telegram ID'), '777')
    await userEvent.type(screen.getByLabelText("Seller's name"), 'Zara')
    await userEvent.click(screen.getByRole('button', { name: 'Add' }))

    await waitFor(() =>
      expect(backend.writes()[0]).toMatchObject({
        method: 'POST',
        path: '/sellers',
        body: {
          name: 'Zara Cosmetics',
          phone: '+998900000000',
          pickup_address: 'Tashkent, Yunusobod 4',
          telegram_id: 777,
          display_name: 'Zara',
        },
      }),
    )
  })

  it('deactivates a seller after confirming', async () => {
    const backend = stubAdminBackend()
    renderSellers()

    const lola = (await screen.findByText('Lola Beauty')).closest('li')!
    await userEvent.click(within(lola).getByRole('button', { name: 'Deactivate' }))
    const dialog = await screen.findByRole('dialog')
    expect(dialog).toHaveTextContent('Deactivate Lola Beauty?')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Deactivate' }))

    await waitFor(() =>
      expect(backend.writes()[0]).toMatchObject({
        method: 'PATCH',
        path: '/sellers/7',
        body: { is_active: false },
      }),
    )
  })

  it('edits a seller in place', async () => {
    const backend = stubAdminBackend()
    renderSellers()

    const lola = (await screen.findByText('Lola Beauty')).closest('li')!
    await userEvent.click(within(lola).getByRole('button', { name: 'Edit' }))
    const name = within(lola).getByLabelText('Shop name')
    await userEvent.clear(name)
    await userEvent.type(name, 'Lola Beauty Pro')
    await userEvent.click(within(lola).getByRole('button', { name: 'Save' }))

    await waitFor(() =>
      expect(backend.writes()[0]).toMatchObject({
        method: 'PATCH',
        path: '/sellers/7',
        body: {
          name: 'Lola Beauty Pro',
          phone: '+998901112233',
          pickup_address: 'Tashkent, Chilonzor 5',
        },
      }),
    )
  })
})

describe('SellersScreen: money (Spec 11)', () => {
  it("shows each seller's rate and what they are owed", async () => {
    stubAdminBackend()
    renderSellers()

    const lola = (await screen.findByText('Lola Beauty')).closest('li')!
    expect(lola).toHaveTextContent('Commission 10%')
    expect(lola).toHaveTextContent('Owed: €27.00')
    expect(screen.getByText('Anor').closest('li')!).toHaveTextContent('Commission 12.5%')
  })

  it('sets the rate of a new seller', async () => {
    const backend = stubAdminBackend()
    renderSellers()

    await userEvent.type(await screen.findByLabelText('Shop name'), 'Zara')
    await userEvent.type(screen.getByLabelText('Pickup address'), 'Yunusobod 4')
    await userEvent.type(screen.getByLabelText('Telegram ID'), '777')
    await userEvent.type(screen.getByLabelText("Seller's name"), 'Zara')
    const rate = screen.getByLabelText('Commission, %')
    await userEvent.clear(rate)
    await userEvent.type(rate, '12.5')
    await userEvent.click(screen.getByRole('button', { name: 'Add' }))

    await waitFor(() =>
      expect(backend.writes()[0]).toMatchObject({
        method: 'POST',
        path: '/sellers',
        body: { commission_percent: '12.5' },
      }),
    )
  })

  it('gives an accountant the money, not the seller controls', async () => {
    stubAdminBackend('accountant')
    renderScreen(
      <AdminMeProvider value={adminMe('accountant')}>
        <SellersScreen />
      </AdminMeProvider>,
      { route: '/admin/sellers', path: '/admin/sellers' },
    )

    const lola = (await screen.findByText('Lola Beauty')).closest('li')!
    expect(within(lola).getByRole('link', { name: 'Money' })).toHaveAttribute(
      'href',
      '/admin/sellers/7',
    )
    expect(screen.queryByRole('heading', { name: 'Add seller' })).not.toBeInTheDocument()
    expect(within(lola).queryByRole('button', { name: 'Edit' })).not.toBeInTheDocument()
    expect(within(lola).queryByRole('button', { name: 'Deactivate' })).not.toBeInTheDocument()
  })
})
