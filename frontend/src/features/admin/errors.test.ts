import { describe, expect, it } from 'vitest'

import { ApiError } from '../../shared/api/client'
import { adminErrorKey, isStatus } from './errors'

describe('adminErrorKey', () => {
  it('prefers the stable code over the status', () => {
    expect(adminErrorKey(new ApiError(409, { detail: 'x', code: 'last_owner' }))).toBe(
      'admin.errors.lastOwner',
    )
    expect(adminErrorKey(new ApiError(409, { detail: 'x', code: 'invalid_state' }))).toBe(
      'admin.errors.invalidState',
    )
  })

  it.each([
    [400, 'admin.errors.badRequest'],
    [403, 'admin.errors.forbidden'],
    [404, 'admin.errors.notFound'],
    [409, 'admin.errors.conflict'],
    [413, 'admin.errors.tooLarge'],
    [422, 'admin.errors.invalid'],
    [500, 'common.error'],
  ])('maps status %i', (status, key) => {
    expect(adminErrorKey(new ApiError(status, { detail: 'x' }))).toBe(key)
  })

  it('falls back for errors that are not API errors', () => {
    expect(adminErrorKey(new TypeError('network'))).toBe('common.error')
    expect(isStatus(new TypeError('x'), 401)).toBe(false)
    expect(isStatus(new ApiError(401, null), 401)).toBe(true)
  })
})
