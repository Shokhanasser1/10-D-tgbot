import type { AdminRole } from './types'

export type AdminSection = 'summary' | 'catalog' | 'orders' | 'couriers' | 'admins'

/** Mirrors the API's role checks, only to decide what to show; the API enforces them. */
const SECTIONS: Record<AdminRole, readonly AdminSection[]> = {
  owner: ['summary', 'catalog', 'orders', 'couriers', 'admins'],
  catalog_manager: ['catalog'],
  dispatcher: ['orders', 'couriers'],
}

export function sectionsFor(role: AdminRole): readonly AdminSection[] {
  return SECTIONS[role]
}

export function canOpen(role: AdminRole, section: AdminSection): boolean {
  return SECTIONS[role].includes(section)
}

/** Where a role lands when it opens /admin. */
export function homeFor(role: AdminRole): AdminSection {
  return SECTIONS[role][0]
}
