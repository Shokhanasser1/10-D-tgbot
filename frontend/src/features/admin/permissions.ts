import type { AdminMe, Permission } from './types'

export type AdminSection =
  'summary' | 'catalog' | 'orders' | 'couriers' | 'sellers' | 'admins' | 'profile'

/** The permission that opens each section. Every admin has a profile. */
const SECTION_PERMISSION: Record<Exclude<AdminSection, 'profile'>, Permission> = {
  summary: 'summary.view',
  catalog: 'catalog.view',
  orders: 'orders.view',
  couriers: 'couriers.view',
  sellers: 'sellers.manage',
  admins: 'admins.manage',
}

const ORDER: readonly AdminSection[] = [
  'summary',
  'catalog',
  'orders',
  'couriers',
  'sellers',
  'admins',
]

/** Only decides what to show; the API enforces the same permissions on every call. */
export function can(me: Pick<AdminMe, 'permissions'>, permission: Permission): boolean {
  return me.permissions.includes(permission)
}

export function sectionsFor(me: Pick<AdminMe, 'permissions'>): readonly AdminSection[] {
  return ORDER.filter((section) =>
    can(me, SECTION_PERMISSION[section as keyof typeof SECTION_PERMISSION]),
  )
}

export function canOpen(me: Pick<AdminMe, 'permissions'>, section: AdminSection): boolean {
  return section === 'profile' || sectionsFor(me).includes(section)
}

/** Where an admin lands when they open /admin. */
export function homeFor(me: Pick<AdminMe, 'permissions'>): AdminSection {
  return sectionsFor(me)[0] ?? 'profile'
}
