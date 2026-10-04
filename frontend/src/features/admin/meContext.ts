import { createContext, useContext } from 'react'

import { can } from './permissions'
import type { AdminMe, Permission } from './types'

const AdminMeContext = createContext<AdminMe | null>(null)

export const AdminMeProvider = AdminMeContext.Provider

/** The signed-in admin, or null outside the admin shell (a screen rendered on its own). */
export function useAdminMeValue(): AdminMe | null {
  return useContext(AdminMeContext)
}

/** A seller's account (Spec 9): it sees only its own products and no seller controls. */
export function useIsSellerAccount(): boolean {
  return useContext(AdminMeContext)?.seller_id != null
}

/**
 * Whether the signed-in admin holds `permission`. Only decides what to show: the API checks
 * the same permission. Outside the admin shell (a screen rendered on its own) everything shows.
 */
export function useCan(permission: Permission): boolean {
  const me = useContext(AdminMeContext)
  return me === null || can(me, permission)
}
