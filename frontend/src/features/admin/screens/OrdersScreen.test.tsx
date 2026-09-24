import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { stubAdminBackend } from '../../../test/mocks/adminBackend'
import { renderScreen } from '../../../test/test-utils'
import { OrdersScreen } from './OrdersScreen'

describe('OrdersScreen', () => {
  it('lists orders with their customer, total, status and warning badges', async () => {
    stubAdminBackend()
    renderScreen(<OrdersScreen />, { route: '/admin/orders', path: '/admin/orders' })

    const first = await screen.findByRole('link', { name: /Order #42/ })
    expect(first).toHaveAttribute('href', '/admin/orders/42')
    expect(first).toHaveTextContent('Aziza K')
    expect(first).toHaveTextContent('€34.97')
    expect(first).toHaveTextContent('Paid')
    expect(first).toHaveTextContent('Out of stock')

    const second = screen.getByRole('link', { name: /Order #41/ })
    expect(second).toHaveTextContent('901') // no name: the Telegram ID instead
    expect(second).toHaveTextContent('Refund failed')
  })

  it('takes its filters from the URL, as the summary links there', async () => {
    const backend = stubAdminBackend()
    renderScreen(<OrdersScreen />, {
      route: '/admin/orders?status=paid',
      path: '/admin/orders',
    })

    await screen.findByRole('link', { name: /Order #42/ })
    expect(backend.requests[0].search.getAll('status')).toEqual(['paid'])
    expect(screen.getByRole('combobox', { name: 'Status' })).toHaveValue('paid')
  })

  it('sends number search, dates and the out-of-stock filter', async () => {
    const backend = stubAdminBackend()
    renderScreen(<OrdersScreen />, { route: '/admin/orders', path: '/admin/orders' })
    await screen.findByRole('link', { name: /Order #42/ })

    await userEvent.type(screen.getByRole('searchbox'), '42')
    await userEvent.type(screen.getByLabelText('From'), '2026-09-01')
    await userEvent.click(screen.getByRole('checkbox', { name: 'Only out-of-stock' }))

    await waitFor(() => {
      const last = backend.requests.at(-1)!.search
      expect([last.get('q'), last.get('from'), last.get('shortfall')]).toEqual([
        '42',
        '2026-09-01',
        'true',
      ])
    })
  })
})
