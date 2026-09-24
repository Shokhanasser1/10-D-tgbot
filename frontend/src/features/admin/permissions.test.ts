import { describe, expect, it } from 'vitest'

import { canOpen, homeFor, sectionsFor } from './permissions'

describe('permissions', () => {
  it('mirrors the API role table', () => {
    expect(sectionsFor('owner')).toEqual(['summary', 'catalog', 'orders', 'couriers', 'admins'])
    expect(sectionsFor('catalog_manager')).toEqual(['catalog'])
    expect(sectionsFor('dispatcher')).toEqual(['orders', 'couriers'])
  })

  it('keeps revenue and admin management for owners', () => {
    for (const role of ['catalog_manager', 'dispatcher'] as const) {
      expect(canOpen(role, 'summary')).toBe(false)
      expect(canOpen(role, 'admins')).toBe(false)
    }
  })

  it('lands each role on its first section', () => {
    expect(homeFor('owner')).toBe('summary')
    expect(homeFor('catalog_manager')).toBe('catalog')
    expect(homeFor('dispatcher')).toBe('orders')
  })
})
