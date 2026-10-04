import { describe, expect, it } from 'vitest'

import { decideLaunch, finishLaunch, isLaunchPending, startLaunch } from './launch'

describe('decideLaunch', () => {
  it.each([
    // isAdmin, isCourier, timedOut, expected
    [true, undefined, false, 'admin'],
    [true, true, false, 'admin'],
    [undefined, true, false, 'deciding'],
    [false, undefined, false, 'deciding'],
    [false, true, false, 'courier'],
    [false, false, false, 'shop'],
    [undefined, undefined, true, 'shop'],
    [undefined, true, true, 'courier'],
    [false, undefined, true, 'shop'],
  ] as const)('admin=%s courier=%s timedOut=%s -> %s', (isAdmin, isCourier, timedOut, expected) => {
    expect(decideLaunch(isAdmin, isCourier, timedOut)).toBe(expected)
  })
})

describe('the once-per-load flag', () => {
  it('is pending only for an app opened at the bare root', () => {
    startLaunch('/')
    expect(isLaunchPending()).toBe(true)

    startLaunch('/orders/12')
    expect(isLaunchPending()).toBe(false)
  })

  it('stays finished once the launch is decided', () => {
    startLaunch('/')
    finishLaunch()
    expect(isLaunchPending()).toBe(false)
  })
})
