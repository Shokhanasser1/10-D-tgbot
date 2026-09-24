import { describe, expect, it } from 'vitest'

import { ATTRIBUTION, DEFAULT_CENTER, parseMapCenter, settingOrDefault, TILE_URL } from './config'

describe('parseMapCenter', () => {
  it('reads "lat,lng"', () => {
    expect(parseMapCenter('41.3,69.2')).toEqual({ latitude: 41.3, longitude: 69.2 })
    expect(parseMapCenter(' -33.9 , 151.2 ')).toEqual({ latitude: -33.9, longitude: 151.2 })
  })

  it.each([
    undefined,
    '',
    '   ',
    '41.3',
    '41.3,',
    ',69.2',
    '41.3,69.2,5',
    'north,east',
    '91,10',
    '10,181',
    'NaN,10',
    'Infinity,10',
  ])('falls back to the default for %j', (raw) => {
    expect(parseMapCenter(raw)).toEqual({ latitude: 52.52, longitude: 13.405 })
  })
})

describe('settingOrDefault', () => {
  it('keeps a real value', () => {
    expect(settingOrDefault('https://tiles.example/{z}/{x}/{y}.png', 'fallback')).toBe(
      'https://tiles.example/{z}/{x}/{y}.png',
    )
  })

  // Docker build args arrive as '' when unset; `??` would have kept the empty string.
  it.each([undefined, '', '   '])('uses the fallback for %j', (raw) => {
    expect(settingOrDefault(raw, 'fallback')).toBe('fallback')
  })
})

describe('map settings from the environment', () => {
  it('are read from the pinned test environment', () => {
    expect(TILE_URL).toBe('https://tiles.test/{z}/{x}/{y}.png')
    expect(ATTRIBUTION).toBe('Test map data')
    expect(DEFAULT_CENTER).toEqual({ latitude: 41.3, longitude: 69.2 })
  })
})
