import type { Pickup } from '../types'

/** "Lola Beauty, Tashkent, Chilonzor 5": where to collect the order (Spec 10). */
export function pickupPlace(pickup: Pickup): string {
  return [pickup.name, pickup.address].filter(Boolean).join(', ')
}
