import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook } from '@testing-library/react'
import type { ReactNode } from 'react'
import { describe, expect, it } from 'vitest'

import { isTrackedOrder, orderRefetchInterval, trackingRefetchInterval, useTracking } from './hooks'
import type { OrderStatus } from './types'

describe('orderRefetchInterval', () => {
  it.each<[OrderStatus | undefined, number | false]>([
    ['pending_payment', 2000],
    ['paid', 10_000],
    ['processing', 10_000],
    ['shipped', 10_000],
    ['delivered', false],
    ['cancelled', false],
    [undefined, false],
  ])('%s -> %s', (status, expected) => {
    expect(orderRefetchInterval(status)).toBe(expected)
  })
})

describe('trackingRefetchInterval', () => {
  it.each([
    ['shipped', 5000],
    ['assigned', 10_000],
    ['processing', 10_000],
    [null, 10_000],
    [undefined, 10_000],
    ['delivered', false],
  ] as const)('%s -> %s', (status, expected) => {
    expect(trackingRefetchInterval(status)).toBe(expected)
  })
})

describe('isTrackedOrder', () => {
  it.each<[OrderStatus | undefined, boolean]>([
    ['pending_payment', false],
    ['cancelled', false],
    [undefined, false],
    ['paid', true],
    ['processing', true],
    ['shipped', true],
    ['delivered', true],
  ])('%s -> %s', (status, expected) => {
    expect(isTrackedOrder(status)).toBe(expected)
  })
})

describe('useTracking', () => {
  function setup(orderStatus: OrderStatus | undefined) {
    const queryClient = new QueryClient()
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    )
    renderHook(() => useTracking(5001, orderStatus), { wrapper })
    return queryClient.getQueryCache().find({ queryKey: ['order', 5001, 'tracking'] })
  }

  // The app-wide staleTime (30 s) would otherwise hide a courier's movement for that long.
  it('never serves stale data', () => {
    expect(setup('shipped')?.observers[0]?.options.staleTime).toBe(0)
  })

  it('is enabled only for orders that have a shipment', () => {
    expect(setup('shipped')?.observers[0]?.options.enabled).toBe(true)
    expect(setup('pending_payment')?.observers[0]?.options.enabled).toBe(false)
  })
})
