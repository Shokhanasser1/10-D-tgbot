import { render, screen } from '@testing-library/react'
import { I18nextProvider } from 'react-i18next'
import { describe, expect, it, vi } from 'vitest'

import i18n from '../../../shared/i18n'
import { shippedDelivery } from '../../../test/fixtures'
import { DeliveryCard } from './DeliveryCard'

function renderCard(overrides: Partial<typeof shippedDelivery>) {
  return render(
    <I18nextProvider i18n={i18n}>
      <DeliveryCard
        delivery={{ ...shippedDelivery, ...overrides }}
        isBusy={false}
        onPickup={vi.fn()}
        onDeliver={vi.fn()}
        onRelease={vi.fn()}
      />
    </I18nextProvider>,
  )
}

describe('DeliveryCard', () => {
  it('tells the courier how much cash to collect', () => {
    renderCard({ cash_to_collect: '198000.00', currency: 'UZS' })

    expect(screen.getByText(/^Collect in cash: UZS.198,000$/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Delivered, cash received' })).toBeInTheDocument()
  })

  it('shows no money for an order paid online', () => {
    renderCard({ cash_to_collect: null })

    expect(screen.queryByText(/Collect in cash/)).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Delivered' })).toBeInTheDocument()
  })
})
