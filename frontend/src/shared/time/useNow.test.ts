import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useNow } from './useNow'

describe('useNow', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-09-24T12:00:00Z'))
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('starts at the current time and moves with the interval', () => {
    const { result } = renderHook(() => useNow(1000))
    const start = result.current

    act(() => {
      vi.advanceTimersByTime(3000)
    })

    expect(result.current - start).toBe(3000)
  })

  it('does not tick between intervals', () => {
    const { result } = renderHook(() => useNow(5000))
    const start = result.current

    act(() => {
      vi.advanceTimersByTime(4999)
    })

    expect(result.current).toBe(start)
  })

  it('stops its timer on unmount', () => {
    const { unmount } = renderHook(() => useNow(1000))

    unmount()

    expect(vi.getTimerCount()).toBe(0)
  })
})
