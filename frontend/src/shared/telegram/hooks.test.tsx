import { renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { useDisableVerticalSwipes } from './hooks'

function stubTelegram(webApp: Record<string, unknown>) {
  window.Telegram = { WebApp: { initData: 'x', ...webApp } } as unknown as Window['Telegram']
}

afterEach(() => {
  delete window.Telegram
})

describe('useDisableVerticalSwipes', () => {
  it('turns swipes off while mounted and back on afterwards', () => {
    const disableVerticalSwipes = vi.fn()
    const enableVerticalSwipes = vi.fn()
    stubTelegram({ disableVerticalSwipes, enableVerticalSwipes, isVersionAtLeast: () => true })

    const { unmount } = renderHook(() => useDisableVerticalSwipes())
    expect(disableVerticalSwipes).toHaveBeenCalledTimes(1)
    expect(enableVerticalSwipes).not.toHaveBeenCalled()

    unmount()
    expect(enableVerticalSwipes).toHaveBeenCalledTimes(1)
  })

  it('asks for Telegram 7.7, the version that introduced the setting', () => {
    const isVersionAtLeast = vi.fn(() => true)
    stubTelegram({ disableVerticalSwipes: vi.fn(), isVersionAtLeast })

    renderHook(() => useDisableVerticalSwipes())

    expect(isVersionAtLeast).toHaveBeenCalledWith('7.7')
  })

  it('does nothing on a client too old to support it', () => {
    const disableVerticalSwipes = vi.fn()
    const enableVerticalSwipes = vi.fn()
    stubTelegram({ disableVerticalSwipes, enableVerticalSwipes, isVersionAtLeast: () => false })

    renderHook(() => useDisableVerticalSwipes()).unmount()

    expect(disableVerticalSwipes).not.toHaveBeenCalled()
    expect(enableVerticalSwipes).not.toHaveBeenCalled()
  })

  it('does nothing outside Telegram', () => {
    expect(() => renderHook(() => useDisableVerticalSwipes()).unmount()).not.toThrow()
  })
})
