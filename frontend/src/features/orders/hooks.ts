import { useQuery } from '@tanstack/react-query'

import { fetchOrder, fetchOrders } from './api'
import type { OrderStatus } from './types'

export function useOrders() {
  return useQuery({ queryKey: ['orders'], queryFn: fetchOrders })
}

const PENDING_POLL_INTERVAL_MS = 2000

export function useOrder(orderId: number) {
  return useQuery({
    queryKey: ['order', orderId],
    queryFn: () => fetchOrder(orderId),
    enabled: Number.isFinite(orderId),
    refetchInterval: (query) => {
      const status = query.state.data?.status as OrderStatus | undefined
      return status === 'pending_payment' ? PENDING_POLL_INTERVAL_MS : false
    },
  })
}
