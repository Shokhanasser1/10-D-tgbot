import { describe, expect, it } from 'vitest'

import { ApiError } from '../../shared/api/client'
import { courierErrorKey, isForbidden } from './errors'

describe('courierErrorKey', () => {
  it.each([
    ['shipment_taken', 'courier.errors.shipmentTaken'],
    ['delivery_limit_reached', 'courier.errors.limitReached'],
    ['invalid_state', 'courier.errors.invalidState'],
  ])('maps the API code %s to %s', (code, key) => {
    expect(courierErrorKey(new ApiError(409, { detail: 'English text', code }))).toBe(key)
  })

  it('treats a missing delivery as gone, whoever it belonged to', () => {
    expect(courierErrorKey(new ApiError(404, { detail: 'Not found' }))).toBe('courier.errors.gone')
  })

  it.each([
    new ApiError(409, { detail: 'x', code: 'some_future_code' }),
    new ApiError(409, { detail: 'x' }),
    new ApiError(409, 'plain text'),
    new ApiError(500, null),
    new Error('network down'),
    'a string',
    undefined,
  ])('falls back to the generic message for %#', (error) => {
    expect(courierErrorKey(error)).toBe('common.error')
  })
})

describe('isForbidden', () => {
  it('is true only for a 403 from the API', () => {
    expect(isForbidden(new ApiError(403, { detail: 'Not a courier' }))).toBe(true)
    expect(isForbidden(new ApiError(401, null))).toBe(false)
    expect(isForbidden(new Error('403'))).toBe(false)
    expect(isForbidden(null)).toBe(false)
  })
})
