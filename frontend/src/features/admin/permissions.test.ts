import { describe, expect, it } from 'vitest'

import { adminMe } from '../../test/adminFixtures'
import { can, canOpen, homeFor, sectionsFor } from './permissions'

describe('permissions', () => {
  it('shows each role the sections its permissions open', () => {
    expect(sectionsFor(adminMe('owner'))).toEqual([
      'summary',
      'catalog',
      'orders',
      'couriers',
      'sellers',
      'admins',
    ])
    expect(sectionsFor(adminMe('manager'))).toEqual([
      'summary',
      'catalog',
      'orders',
      'couriers',
      'sellers',
    ])
    expect(sectionsFor(adminMe('catalog_manager'))).toEqual(['catalog'])
    expect(sectionsFor(adminMe('dispatcher'))).toEqual(['orders', 'couriers'])
    expect(sectionsFor(adminMe('accountant'))).toEqual(['summary', 'orders'])
    expect(sectionsFor(adminMe('viewer'))).toEqual(['summary', 'catalog', 'orders', 'couriers'])
    // Spec 9: a seller works in the catalog only, and lands there.
    expect(sectionsFor(adminMe('seller'))).toEqual(['catalog'])
    expect(homeFor(adminMe('seller'))).toBe('catalog')
  })

  it('keeps admin management for owners and lets everyone open their profile', () => {
    for (const role of [
      'manager',
      'catalog_manager',
      'dispatcher',
      'accountant',
      'viewer',
    ] as const) {
      expect(canOpen(adminMe(role), 'admins')).toBe(false)
      expect(canOpen(adminMe(role), 'profile')).toBe(true)
    }
  })

  it('gives a viewer nothing to change', () => {
    const viewer = adminMe('viewer')
    for (const permission of ['catalog.edit', 'couriers.manage', 'orders.cancel_unpaid'] as const) {
      expect(can(viewer, permission)).toBe(false)
    }
  })

  it('lands each role on its first section, or the profile when it has none', () => {
    expect(homeFor(adminMe('owner'))).toBe('summary')
    expect(homeFor(adminMe('dispatcher'))).toBe('orders')
    expect(homeFor({ permissions: [] })).toBe('profile')
  })
})
