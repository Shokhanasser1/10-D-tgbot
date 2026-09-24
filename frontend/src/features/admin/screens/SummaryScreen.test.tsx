import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { stubAdminBackend } from '../../../test/mocks/adminBackend'
import { renderScreen } from '../../../test/test-utils'
import { SummaryScreen } from './SummaryScreen'

describe('SummaryScreen', () => {
  it('shows the key numbers, stock warnings and top sellers', async () => {
    stubAdminBackend()
    renderScreen(<SummaryScreen />)

    expect(await screen.findByText('€104.91')).toBeInTheDocument()
    expect(screen.getByText('3')).toBeInTheDocument()
    expect(screen.getByText('€34.97')).toBeInTheDocument()
    expect(screen.getByText('0 left')).toBeInTheDocument()
    expect(screen.getByText('4 sold')).toBeInTheDocument()
  })

  it('links each status count to the filtered order list', async () => {
    stubAdminBackend()
    renderScreen(<SummaryScreen />)

    const paid = await screen.findByRole('link', { name: /Paid/ })
    expect(paid).toHaveAttribute('href', '/admin/orders?status=paid')
    expect(paid).toHaveTextContent('2')
  })

  it('links a low-stock item to its product', async () => {
    stubAdminBackend()
    renderScreen(<SummaryScreen />)

    const item = await screen.findByRole('link', { name: /LIP-VELVET-RED/ })
    expect(item).toHaveAttribute('href', '/admin/catalog/products/1')
  })

  it('asks for the chosen period', async () => {
    const backend = stubAdminBackend()
    renderScreen(<SummaryScreen />)
    await screen.findByText('€104.91')

    await userEvent.click(screen.getByRole('tab', { name: '30 days' }))

    await waitFor(() =>
      expect(backend.requests.map((r) => r.search.get('period'))).toEqual(['today', '30d']),
    )
    expect(screen.getByRole('tab', { name: '30 days' })).toHaveAttribute('aria-selected', 'true')
  })
})
