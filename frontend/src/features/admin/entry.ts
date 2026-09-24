import { useQuery } from '@tanstack/react-query'

import { ApiError, apiFetch } from '../../shared/api/client'

/**
 * Whether the current user may open the admin panel. Kept apart from the panel's own code so
 * the storefront shell can ask without pulling the admin chunk into the first load. Most users
 * are shoppers, for whom the API answers 401/403: a value, not an error.
 */
async function isAdmin(): Promise<boolean> {
  try {
    await apiFetch('/internal/me', { admin: true })
    return true
  } catch (error) {
    if (error instanceof ApiError && (error.status === 401 || error.status === 403)) return false
    throw error
  }
}

export function useIsAdmin() {
  return useQuery({
    queryKey: ['admin-entry'],
    queryFn: isAdmin,
    retry: false,
    staleTime: 5 * 60_000,
  })
}
