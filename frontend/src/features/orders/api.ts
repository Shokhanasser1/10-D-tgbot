import { apiFetch } from '../../shared/api/client'
import type { OrderDetail, OrderListItem, Tracking } from './types'

export function fetchOrders(): Promise<OrderListItem[]> {
  return apiFetch<OrderListItem[]>('/orders')
}

export function fetchOrder(orderId: number): Promise<OrderDetail> {
  return apiFetch<OrderDetail>(`/orders/${orderId}`)
}

export function fetchTracking(orderId: number): Promise<Tracking> {
  return apiFetch<Tracking>(`/orders/${orderId}/tracking`)
}
