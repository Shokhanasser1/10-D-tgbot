import type { AdminMe, Permission } from './types'

export type AdminSection =
  'summary' | 'catalog' | 'orders' | 'earnings' | 'couriers' | 'sellers' | 'admins' | 'profile'

type Who = Pick<AdminMe, 'permissions'> & Partial<Pick<AdminMe, 'seller_id'>>

/** Only decides what to show; the API enforces the same permissions on every call. */
export function can(me: Pick<AdminMe, 'permissions'>, permission: Permission): boolean {
  return me.permissions.includes(permission)
}

const isSeller = (me: Who) => me.seller_id != null

/** What opens each section. Every admin has a profile. */
const SECTION_RULE: Record<Exclude<AdminSection, 'profile'>, (me: Who) => boolean> = {
  summary: (me) => can(me, 'summary.view'),
  catalog: (me) => can(me, 'catalog.view'),
  // A seller's Orders are their own (Spec 10): opened by preparing orders, not the platform view.
  orders: (me) => (isSeller(me) ? can(me, 'orders.prepare') : can(me, 'orders.view')),
  // A seller's own money (Spec 11).
  earnings: (me) => isSeller(me),
  couriers: (me) => can(me, 'couriers.view'),
  // Those who pay sellers out see the list too, read-only (Spec 11).
  sellers: (me) => can(me, 'sellers.manage') || can(me, 'payouts.manage'),
  admins: (me) => can(me, 'admins.manage'),
}

const ORDER: readonly Exclude<AdminSection, 'profile'>[] = [
  'summary',
  'catalog',
  'orders',
  'earnings',
  'couriers',
  'sellers',
  'admins',
]

export function sectionsFor(me: Who): readonly AdminSection[] {
  return ORDER.filter((section) => SECTION_RULE[section](me))
}

export function canOpen(me: Who, section: AdminSection): boolean {
  return section === 'profile' || sectionsFor(me).includes(section)
}

/** Where an admin lands when they open /admin. */
export function homeFor(me: Who): AdminSection {
  return sectionsFor(me)[0] ?? 'profile'
}
