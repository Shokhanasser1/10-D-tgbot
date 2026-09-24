import type { Coordinates, DeliveryAddress } from '../../shared/types'

export type OrderStatus =
  'pending_payment' | 'paid' | 'processing' | 'shipped' | 'delivered' | 'cancelled'

export type ShipmentStatus = 'processing' | 'assigned' | 'shipped' | 'delivered'

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
  shipment_status: ShipmentStatus | null
}

export interface TrackingLocation {
  latitude: number
  longitude: number
  updated_at: string
  /** Decided by the server, so every client agrees on what "stale" means. */
  is_stale: boolean
}

export interface Tracking {
  /** Null until the order has a shipment, i.e. for a moment after payment. */
  status: ShipmentStatus | null
  courier: { name: string } | null
  courier_location: TrackingLocation | null
  destination: Coordinates | null
  picked_up_at: string | null
  delivered_at: string | null
}
