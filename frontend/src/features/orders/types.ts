import type { DeliveryAddress } from '../../shared/types'

export type OrderStatus =
  'pending_payment' | 'paid' | 'processing' | 'shipped' | 'delivered' | 'cancelled'

export interface OrderListItem {
  id: number
  status: OrderStatus
  currency: string
  total: string
  placed_at: string
}

export interface OrderItem {
  id: number
  variant_id: number
  product_name_snapshot: string
  qty: number
  unit_price_snapshot: string
}

export interface OrderDetail {
  id: number
  status: OrderStatus
  currency: string
  subtotal: string
  shipping_cost: string
  total: string
  delivery_address: DeliveryAddress
  placed_at: string
  items: OrderItem[]
  payment_status: string | null
  shipment_status: string | null
}
