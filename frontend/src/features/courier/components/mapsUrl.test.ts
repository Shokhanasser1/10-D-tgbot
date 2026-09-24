import { describe, expect, it } from 'vitest'

import { mapsUrl, telHref } from './mapsUrl'

const address = {
  street: 'Alexanderplatz 1',
  city: 'Berlin',
  postal_code: '10178',
  country: 'DE',
  phone: '+49 123 4567',
  notes: null,
}

describe('mapsUrl', () => {
  it('uses the pin when there is one', () => {
    const url = new URL(mapsUrl({ address, destination: { latitude: 52.52, longitude: 13.405 } }))

    expect(url.origin + url.pathname).toBe('https://www.google.com/maps/search/')
    expect(url.searchParams.get('query')).toBe('52.52,13.405')
  })

  it('falls back to the address, skipping empty parts', () => {
    const url = new URL(mapsUrl({ address: { ...address, postal_code: '' }, destination: null }))

    expect(url.searchParams.get('query')).toBe('Alexanderplatz 1, Berlin, DE')
  })

  it('encodes what the customer typed, so it cannot inject query parameters', () => {
    const url = new URL(mapsUrl({ address: { ...address, street: 'A&b=c#d' }, destination: null }))

    expect(url.searchParams.get('query')).toContain('A&b=c#d')
    expect([...url.searchParams.keys()]).toEqual(['api', 'query'])
  })
})

describe('telHref', () => {
  it.each([
    ['+49 123 4567', 'tel:+491234567'],
    ['(030) 123-45', 'tel:03012345'],
    ['+998 90 111 22 33', 'tel:+998901112233'],
  ])('dials %s as %s', (phone, expected) => {
    expect(telHref(phone)).toBe(expected)
  })

  it.each(['', 'call me', '+', 'javascript:alert(1)'.replace(/\d/g, '')])(
    'gives no link for %j',
    (phone) => {
      expect(telHref(phone)).toBeNull()
    },
  )
})
