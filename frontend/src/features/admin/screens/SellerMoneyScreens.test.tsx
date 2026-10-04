import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { stubAdminBackend } from '../../../test/mocks/adminBackend'
import { renderScreen } from '../../../test/test-utils'
import { SellerLedgerScreen, SellerMoneyScreen } from './SellerMoneyScreens'

describe('SellerLedgerScreen (Spec 11)', () => {
  function renderLedger() {
    return renderScreen(<SellerLedgerScreen />, {
      route: '/admin/sellers/7',
      path: '/admin/sellers/:sellerId',
    })
  }

  it('shows the balance, earnings by order and payouts', async () => {
    stubAdminBackend()
    renderLedger()

    expect(await screen.findByRole('heading', { name: 'Lola Beauty' })).toBeInTheDocument()
    expect(screen.getByText('€34.00')).toBeInTheDocument()
    expect(screen.getByText('Order #43')).toBeInTheDocument()
    expect(screen.getAllByText('Goods €30.00 − 10% commission (€3.00)')).toHaveLength(2)
    expect(screen.getByText('Card *1234')).toBeInTheDocument()
  })

  it('records a payout', async () => {
    const backend = stubAdminBackend()
    renderLedger()

    await userEvent.type(await screen.findByLabelText('Amount'), '20.50')
    await userEvent.type(screen.getByLabelText('Note (how it was paid)'), 'Cash')
    await userEvent.click(screen.getByRole('button', { name: 'Record payout' }))

    await waitFor(() =>
      expect(backend.writes()[0]).toMatchObject({
        method: 'POST',
        path: '/sellers/7/payouts',
        body: { amount: '20.50', currency: 'EUR', note: 'Cash' },
      }),
    )
  })
})

describe('SellerMoneyScreen (Spec 11)', () => {
  it('shows a seller their balance, earnings and payouts, with nothing to record', async () => {
    stubAdminBackend('seller')
    renderScreen(<SellerMoneyScreen />, { route: '/admin/earnings', path: '/admin/earnings' })

    expect(await screen.findByText('€34.00')).toBeInTheDocument()
    expect(screen.getByText('Order #42')).toBeInTheDocument()
    expect(screen.getByText('Card *1234')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Record payout' })).not.toBeInTheDocument()
  })
})
