import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook } from '@testing-library/react'
import type { ReactNode } from 'react'
import { describe, expect, it } from 'vitest'

import { courierKeys, useCourierDeliveries, useCourierPool, useCourierProfile } from './hooks'

function setup() {
  const queryClient = new QueryClient()
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  // Polling and staleness live on the observer (the hook), not on the cached query.
  const optionsOf = (queryKey: readonly unknown[]) =>
    queryClient.getQueryCache().find({ queryKey })?.observers[0]?.options
  return { queryClient, wrapper, optionsOf }
}

// The polling cadence is a product decision (how quickly a courier sees a new order, and how
// often GPS freshness updates), so it is pinned rather than left implicit.
describe('courier query configuration', () => {
  it('polls the pool every 10 s and never serves it stale', () => {
    const { wrapper, optionsOf } = setup()
    renderHook(() => useCourierPool(), { wrapper })

    const options = optionsOf(courierKeys.pool)
    expect(options?.refetchInterval).toBe(10_000)
    expect(options?.staleTime).toBe(0)
  })

  it('polls deliveries every 5 s and never serves them stale', () => {
    const { wrapper, optionsOf } = setup()
    renderHook(() => useCourierDeliveries(), { wrapper })

    const options = optionsOf(courierKeys.deliveries)
    expect(options?.refetchInterval).toBe(5_000)
    expect(options?.staleTime).toBe(0)
  })

  it('does not retry the profile, since a 403 there is an answer, not a fault', () => {
    const { wrapper, optionsOf } = setup()
    renderHook(() => useCourierProfile(), { wrapper })

    const options = optionsOf(courierKeys.profile)
    expect(options?.retry).toBe(false)
    expect(options?.staleTime).toBeGreaterThan(60_000)
  })

  it('does not fetch the pool or deliveries when disabled', () => {
    const { queryClient, wrapper } = setup()
    renderHook(() => useCourierPool(false), { wrapper })
    renderHook(() => useCourierDeliveries(false), { wrapper })

    expect(queryClient.isFetching()).toBe(0)
  })
})
