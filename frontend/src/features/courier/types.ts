import type { Coordinates } from '../../shared/types'

export type CourierTab = 'pool' | 'mine'

export interface CourierProfile {
  id: number
  name: string
  bot_username: string | null
  max_active_deliveries: number
}

/** Where the courier collects an order: the seller's shop (Spec 10). */
export interface Pickup {
  name: string
  address: string | null
  phone: string | null
}

/** A claimable order. Deliberately without phone, notes or coordinates. */
export interface PoolItem {
  shipment_id: number
  order_id: number
  city: string
  street: string
  item_count: number
  placed_at: string
  /** Cash on delivery: what the courier collects. Null for orders paid online. */
  cash_to_collect?: string | null
  currency?: string
  pickup: Pickup
}

export interface DeliveryLine {
  name: string
  qty: number
}

export interface CourierAddress {
  street: string
  city: string
  postal_code: string
  country: string
  phone: string
  notes: string | null
}

export type DeliveryStatus = 'assigned' | 'shipped'

export interface CourierDelivery {
  shipment_id: number
  order_id: number
  status: DeliveryStatus
  address: CourierAddress
  destination: Coordinates | null
  items: DeliveryLine[]
  assigned_at: string | null
  picked_up_at: string | null
  cash_to_collect?: string | null
  currency?: string
  pickup: Pickup
}

export interface CourierDeliveries {
  /** When the courier's GPS last reached the server; one value for all their deliveries. */
  location_updated_at: string | null
  deliveries: CourierDelivery[]
}

export interface ShipmentAction {
  shipment_id: number
  order_id: number
  status: string
}
