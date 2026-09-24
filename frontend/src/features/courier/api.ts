import { ApiError, apiFetch } from '../../shared/api/client'
import type { CourierDeliveries, CourierProfile, PoolItem, ShipmentAction } from './types'

/**
 * Null means "this Telegram user is not a courier" (the API answers 403). That is the normal
 * case for every customer, so it is a value rather than an error: no retries, no red logs.
 */
export async function getCourierProfile(): Promise<CourierProfile | null> {
  try {
    return await apiFetch<CourierProfile>('/courier/me')
  } catch (error) {
    if (error instanceof ApiError && error.status === 403) return null
    throw error
  }
}

export function fetchPool(): Promise<PoolItem[]> {
  return apiFetch<PoolItem[]>('/courier/pool')
}

export function fetchDeliveries(): Promise<CourierDeliveries> {
  return apiFetch<CourierDeliveries>('/courier/deliveries')
}

function act(step: 'claim' | 'release' | 'pickup' | 'deliver') {
  return (shipmentId: number) =>
    apiFetch<ShipmentAction>(`/courier/deliveries/${shipmentId}/${step}`, { method: 'POST' })
}

export const claimDelivery = act('claim')
export const releaseDelivery = act('release')
export const pickupDelivery = act('pickup')
export const deliverDelivery = act('deliver')
