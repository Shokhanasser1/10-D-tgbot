import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  claimDelivery,
  deliverDelivery,
  fetchDeliveries,
  fetchPool,
  getCourierProfile,
  pickupDelivery,
  releaseDelivery,
} from './api'

export const courierKeys = {
  profile: ['courier', 'profile'] as const,
  pool: ['courier', 'pool'] as const,
  deliveries: ['courier', 'deliveries'] as const,
}

const PROFILE_STALE_MS = 5 * 60_000
const POOL_POLL_MS = 10_000
const DELIVERIES_POLL_MS = 5_000

export function useCourierProfile() {
  return useQuery({
    queryKey: courierKeys.profile,
    queryFn: getCourierProfile,
    retry: false,
    staleTime: PROFILE_STALE_MS,
  })
}

// `staleTime: 0` overrides the app-wide default so a poll always reaches the server.
export function useCourierPool(enabled = true) {
  return useQuery({
    queryKey: courierKeys.pool,
    queryFn: fetchPool,
    enabled,
    refetchInterval: POOL_POLL_MS,
    staleTime: 0,
  })
}

export function useCourierDeliveries(enabled = true) {
  return useQuery({
    queryKey: courierKeys.deliveries,
    queryFn: fetchDeliveries,
    enabled,
    refetchInterval: DELIVERIES_POLL_MS,
    staleTime: 0,
  })
}

function useDeliveryAction(action: (shipmentId: number) => Promise<unknown>) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: action,
    // Also on failure: a "someone else took it" 409 is exactly when the pool has changed.
    onSettled: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: courierKeys.pool }),
        queryClient.invalidateQueries({ queryKey: courierKeys.deliveries }),
      ]),
  })
}

export function useCourierActions() {
  const claim = useDeliveryAction(claimDelivery)
  const release = useDeliveryAction(releaseDelivery)
  const pickup = useDeliveryAction(pickupDelivery)
  const deliver = useDeliveryAction(deliverDelivery)

  const pending = [claim, release, pickup, deliver].find((mutation) => mutation.isPending)

  return {
    claim,
    release,
    pickup,
    deliver,
    /** The shipment an action is currently running for, so only its card is disabled. */
    busyShipmentId: pending ? (pending.variables as number) : null,
  }
}
