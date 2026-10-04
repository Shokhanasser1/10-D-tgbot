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

type Who = Pick<AdminMe, 'permissions'> & Partial<Pick<AdminMe, 'seller_id'>>

/** Only decides what to show; the API enforces the same permissions on every call. */
export function can(me: Pick<AdminMe, 'permissions'>, permission: Permission): boolean {
  return me.permissions.includes(permission)
}

function opens(me: Who, section: Exclude<AdminSection, 'profile'>): boolean {
  // A seller's Orders are their own (Spec 10): opened by preparing orders, not the platform view.
  if (section === 'orders' && me.seller_id != null) return can(me, 'orders.prepare')
  return can(me, SECTION_PERMISSION[section])
}

export function sectionsFor(me: Who): readonly AdminSection[] {
  return ORDER.filter((section) => opens(me, section as Exclude<AdminSection, 'profile'>))
}

export function canOpen(me: Who, section: AdminSection): boolean {
  return section === 'profile' || sectionsFor(me).includes(section)
}

/** Where an admin lands when they open /admin. */
export function homeFor(me: Who): AdminSection {
  return sectionsFor(me)[0] ?? 'profile'
}
