import { describe, expect, it } from 'vitest'

import { formatMoney } from './formatMoney'

describe('formatMoney', () => {
  it('shows sums without decimals', () => {
    expect(formatMoney('250000.00', 'UZS', 'en')).toBe('UZS 250,000')
  })

  it('keeps cents for currencies that use them', () => {
    expect(formatMoney('19.9', 'EUR', 'en')).toBe('€19.90')
  })
})
