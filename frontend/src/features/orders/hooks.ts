import { useQuery } from '@tanstack/react-query'

import { fetchOrder, fetchOrders, fetchTracking } from './api'
import type { OrderStatus, ShipmentStatus } from './types'

export function useOrders() {
  return useQuery({ queryKey: ['orders'], queryFn: fetchOrders })
}

const PENDING_POLL_INTERVAL_MS = 2000
const ACTIVE_POLL_INTERVAL_MS = 10_000
const LIVE_TRACKING_POLL_INTERVAL_MS = 5000

/** Orders that have a shipment worth showing a tracking card for. */
const TRACKED_STATUSES: readonly OrderStatus[] = ['paid', 'processing', 'shipped', 'delivered']

export function isTrackedOrder(status: OrderStatus | undefined): boolean {
  return status !== undefined && TRACKED_STATUSES.includes(status)
}

/**
 * How often to re-read an order: quickly while waiting for Stripe's webhook, slowly while it is
 * being fulfilled (so the status badge follows the courier), and not at all once it is final.
 * A plain function so the schedule can be tested without waiting on timers.
 */
export function orderRefetchInterval(status: OrderStatus | undefined): number | false {
  if (status === 'pending_payment') return PENDING_POLL_INTERVAL_MS
  if (status === 'paid' || status === 'processing' || status === 'shipped') {
    return ACTIVE_POLL_INTERVAL_MS
  }
  return false
}

/** Fast while the courier's position is live, slow while waiting, off once delivered. */
export function trackingRefetchInterval(status: ShipmentStatus | null | undefined): number | false {
  if (status === 'shipped') return LIVE_TRACKING_POLL_INTERVAL_MS
  if (status === 'delivered') return false
  return ACTIVE_POLL_INTERVAL_MS
}

export function useOrder(orderId: number) {
  return useQuery({
    queryKey: ['order', orderId],
    queryFn: () => fetchOrder(orderId),
    enabled: Number.isFinite(orderId),
    refetchInterval: (query) => orderRefetchInterval(query.state.data?.status),
  })
}

export function useTracking(orderId: number, orderStatus: OrderStatus | undefined) {
  return useQuery({
    queryKey: ['order', orderId, 'tracking'],
    queryFn: () => fetchTracking(orderId),
    enabled: Number.isFinite(orderId) && isTrackedOrder(orderStatus),
    // The app-wide staleTime would hide a courier's movement for half a minute.
    staleTime: 0,
    refetchInterval: (query) => trackingRefetchInterval(query.state.data?.status),
  })
}
