import { describe, expect, it } from 'vitest'

import { courierIcon, destinationIcon, staleCourierIcon } from './markerIcons'

describe('marker icons', () => {
  it.each([
    ['destination', destinationIcon],
    ['courier', courierIcon],
    ['stale courier', staleCourierIcon],
  ])('the %s marker is drawn with HTML, never with an image URL', (_name, icon) => {
    // Image URLs are what Leaflet's default icon resolves from its stylesheet, and what a
    // bundler breaks; a `divIcon` needs none.
    expect(icon.options).not.toHaveProperty('iconUrl')
    expect(typeof icon.options.html).toBe('string')
  })

  it("does not fall back to Leaflet's default white-square class", () => {
    for (const icon of [destinationIcon, courierIcon, staleCourierIcon]) {
      expect(icon.options.className).toBeTruthy()
      expect(icon.options.className).not.toContain('leaflet-div-icon')
    }
  })

  it('draws a stale courier differently from a live one', () => {
    expect(staleCourierIcon.options.html).not.toEqual(courierIcon.options.html)
  })
})
