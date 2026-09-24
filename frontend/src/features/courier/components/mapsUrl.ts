import type { CourierDelivery } from '../types'

/**
 * Universal Google Maps link: opens the app on phones and the site elsewhere. It uses the
 * customer's pin when there is one and falls back to the typed address.
 */
export function mapsUrl({
  destination,
  address,
}: Pick<CourierDelivery, 'destination' | 'address'>) {
  const query = destination
    ? `${destination.latitude},${destination.longitude}`
    : [address.street, address.city, address.postal_code, address.country]
        .filter(Boolean)
        .join(', ')

  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(query)}`
}

/** A `tel:` link needs digits and an optional leading plus; the rest is typing decoration. */
export function telHref(phone: string): string | null {
  const dialable = phone.replace(/[^\d+]/g, '')
  return /\d/.test(dialable) ? `tel:${dialable}` : null
}
