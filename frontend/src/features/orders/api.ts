import { apiFetch } from '../../shared/api/client'
import type { OrderDetail, OrderListItem } from './types'

export function fetchOrders(): Promise<OrderListItem[]> {
  return apiFetch<OrderListItem[]>('/orders')
}

export function fetchOrder(orderId: number): Promise<OrderDetail> {
  return apiFetch<OrderDetail>(`/orders/${orderId}`)
}
