import type { OrderStatus } from '../orders/types'
import type { DeliveryAddress } from '../../shared/types'

export type AdminRole =
  'owner' | 'manager' | 'catalog_manager' | 'dispatcher' | 'accountant' | 'viewer' | 'seller'

export type Permission =
  | 'summary.view'
  | 'catalog.view'
  | 'catalog.edit'
  | 'orders.view'
  | 'orders.cancel_unpaid'
  | 'orders.cancel_paid'
  | 'refunds.manage'
  | 'couriers.view'
  | 'couriers.manage'
  | 'admins.manage'
  | 'taxonomy.edit'
  | 'sellers.manage'

export interface AdminMe {
  /** Null only for the internal token, which the UI never uses. */
  telegram_id: number | null
  display_name: string
  role: AdminRole
  /** What this admin may do; the API checks the same permissions on every call. */
  permissions: Permission[]
  login: string | null
  has_password: boolean
  /** After an owner's reset: nothing but the profile until a new password is set. */
  must_change_password: boolean
  /** Set for a seller's account (Spec 9): its panel holds only that seller's products. */
  seller_id: number | null
  seller_name: string | null
}

export interface PasswordReset {
  login: string
  /** Shown once; the admin must replace it at the next sign-in. */
  temporary_password: string
}

/** Fields the Telegram Login Widget hands to its callback, passed to the API untouched. */
export interface TelegramLoginData {
  id: number
  auth_date: number
  hash: string
  first_name?: string
  last_name?: string
  username?: string
  photo_url?: string
}

export interface Admin {
  id: number
  telegram_id: number
  role: AdminRole
  display_name: string
  is_active: boolean
  created_at: string
  created_by: number | null
  login?: string | null
  has_password?: boolean
  /** Seller accounts only; they are managed under Sellers. */
  seller_id?: number | null
}

// --- sellers (Spec 9) ------------------------------------------------------------------------

export interface SellerAccount {
  id: number
  telegram_id: number
  display_name: string
  is_active: boolean
}

export interface AdminSeller {
  id: number
  name: string
  phone: string | null
  pickup_address: string | null
  is_active: boolean
  /** Empty unless the admin may manage sellers. */
  accounts: SellerAccount[]
  product_count: number
}

export interface SellerInput {
  name: string
  phone: string | null
  pickup_address: string
  telegram_id: number
  display_name: string
}

export type SellerUpdate = Partial<Pick<AdminSeller, 'name' | 'phone' | 'is_active'>> & {
  pickup_address?: string
}

// --- catalog ---------------------------------------------------------------------------------

export type ProductStatus = 'draft' | 'active' | 'archived'
export type AttributeValueType = 'text' | 'number' | 'boolean' | 'color'

/** locale -> field -> value */
export type Translations = Record<string, Record<string, string>>

export interface AdminCategory {
  id: number
  slug: string
  parent_id: number | null
  sort_order: number
  name: string
  translations: Translations
}

export interface AdminAttribute {
  id: number
  key: string
  category_id: number
  value_type: AttributeValueType
  translations: Translations
}

export interface AdminProductListItem {
  id: number
  category_id: number
  seller_id: number
  seller_name: string
  base_sku: string
  base_price: string
  status: ProductStatus
  name: string
  thumbnail_url: string | null
  variant_count: number
  min_price: string | null
  total_stock: number
}

export interface Page<T> {
  items: T[]
  total: number
}

export interface AdminVariant {
  id: number
  product_id: number
  sku: string
  price: string
  stock_qty: number
  attribute_values: Record<string, string>
}

export interface AdminImage {
  id: number
  product_id: number
  variant_id: number | null
  url: string
  position: number
}

export interface AdminProduct {
  id: number
  category_id: number
  seller_id: number
  seller_name: string
  base_sku: string
  base_price: string
  status: ProductStatus
  name: string
  translations: Translations
  variants: AdminVariant[]
  images: AdminImage[]
}

export interface ProductInput {
  category_id: number
  /** Platform staff choose it; a seller's products are always their own (Spec 9). */
  seller_id?: number
  base_sku: string
  base_price: string
  status: ProductStatus
}

export interface VariantInput {
  sku: string
  price: string
  stock_qty: number
  attribute_values: Record<string, string>
}

export interface TranslationInput {
  entity_type: 'product' | 'category' | 'attribute'
  entity_id: number
  locale: string
  field: string
  value: string
}

// --- orders ----------------------------------------------------------------------------------

export type AdminShipmentStatus = 'processing' | 'assigned' | 'shipped' | 'delivered' | 'cancelled'
export type RefundStatus = 'pending' | 'succeeded' | 'failed' | 'manual_required'

export type PaymentMethod = 'telegram' | 'cash' | 'stripe'

export interface AdminOrderListItem {
  id: number
  status: OrderStatus
  currency: string
  total: string
  placed_at: string
  telegram_id: number
  customer_name: string | null
  shipment_status: AdminShipmentStatus | null
  stock_shortfall: boolean
  refund_status: RefundStatus | null
  payment_method?: PaymentMethod
}

export interface AdminOrderItem {
  id: number
  variant_id: number
  sku: string
  product_id: number
  product_name_snapshot: string
  qty: number
  unit_price_snapshot: string
}

export interface AdminOrder {
  id: number
  status: OrderStatus
  currency: string
  subtotal: string
  shipping_cost: string
  total: string
  delivery_address: DeliveryAddress
  placed_at: string
  customer: {
    telegram_id: number
    first_name: string | null
    last_name: string | null
    username: string | null
  }
  items: AdminOrderItem[]
  payment: {
    method?: PaymentMethod
    status: string
    amount: string
    refund_status: RefundStatus | null
    /** Telegram Payments: to find the payment in the Click/Payme cabinet. */
    telegram_payment_charge_id?: string | null
    provider_payment_charge_id?: string | null
  } | null
  shipment: {
    id: number
    status: AdminShipmentStatus
    courier_id: number | null
    courier_name: string | null
    assigned_at: string | null
    picked_up_at: string | null
    delivered_at: string | null
  } | null
  stock_shortfall: boolean
  cancelled_at: string | null
  cancelled_by: number | null
  cancel_reason: string | null
  can_cancel: boolean
}

export interface OrderFilters {
  status?: OrderStatus[]
  q?: string
  from?: string
  to?: string
  shortfall?: boolean
  offset?: number
}

// --- couriers --------------------------------------------------------------------------------

export interface AdminCourier {
  id: number
  telegram_id: number
  name: string
  phone: string | null
  is_active: boolean
  active_deliveries: number
}

export interface AdminShipment {
  id: number
  order_id: number
  status: AdminShipmentStatus
  courier_id: number | null
  courier_name: string | null
  assigned_at: string | null
  picked_up_at: string | null
}

export interface CourierLocation {
  courier_id: number
  name: string
  latitude: number
  longitude: number
  updated_at: string
  is_stale: boolean
  active_deliveries: number
}

// --- summary ---------------------------------------------------------------------------------

export type StatsPeriod = 'today' | '7d' | '30d'

export interface Summary {
  period: StatsPeriod
  currency: string
  revenue: string
  orders_count: number
  average_order: string
  status_counts: Record<OrderStatus, number>
  low_stock: {
    variant_id: number
    product_id: number
    sku: string
    name: string
    stock_qty: number
  }[]
  top_products: { product_id: number; name: string; qty: number; revenue: string }[]
}
