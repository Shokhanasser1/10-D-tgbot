import type { SellerBrief } from '../catalog/types'

export interface CartItem {
  id: number
  variant_id: number
  sku: string
  product_name: string
  thumbnail_url: string | null
  qty: number
  unit_price_snapshot: string
  line_total: string
}

export interface Cart {
  items: CartItem[]
  subtotal: string
  /** Whose products the cart holds: one seller at a time (Spec 9). Null when empty. */
  seller: SellerBrief | null
}
