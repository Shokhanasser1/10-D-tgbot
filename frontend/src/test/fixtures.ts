import type { Cart } from '../features/cart/types'
import type { Category, ProductDetail, ProductListItem } from '../features/catalog/types'
import type { CourierDelivery, CourierProfile, PoolItem } from '../features/courier/types'
import type { OrderDetail, OrderListItem, Tracking } from '../features/orders/types'

export const categories: Category[] = [
  { id: 1, slug: 'lipstick', parent_id: null, sort_order: 0, name: 'Lipstick' },
  { id: 2, slug: 'serums', parent_id: null, sort_order: 1, name: 'Serums' },
]

export const products: ProductListItem[] = [
  {
    id: 1,
    category_id: 1,
    seller: { id: 7, name: 'Lola Beauty' },
    base_sku: 'LIP-VELVET',
    base_price: '19.99',
    name: 'Velvet Matte Lipstick',
    thumbnail_url: null,
  },
  {
    id: 2,
    category_id: 2,
    seller: { id: 8, name: 'Anor' },
    base_sku: 'SERUM-VITC',
    base_price: '24.50',
    name: 'Vitamin C Serum',
    thumbnail_url: null,
  },
]

export const productDetail: ProductDetail = {
  id: 1,
  category_id: 1,
  seller: { id: 7, name: 'Lola Beauty' },
  base_sku: 'LIP-VELVET',
  base_price: '19.99',
  name: 'Velvet Matte Lipstick',
  description: 'Long-lasting matte finish.',
  image_urls: [],
  variants: [
    {
      id: 11,
      sku: 'LIP-VELVET-RED',
      price: '19.99',
      stock_qty: 5,
      attribute_values: { shade: 'red' },
      image_urls: [],
    },
    {
      id: 13,
      sku: 'LIP-VELVET-BERRY',
      price: '22.00',
      stock_qty: 3,
      attribute_values: { shade: 'berry' },
      image_urls: [],
    },
  ],
}

export const cart: Cart = {
  items: [
    {
      id: 101,
      variant_id: 11,
      sku: 'LIP-VELVET-RED',
      product_name: 'Velvet Matte Lipstick',
      thumbnail_url: null,
      qty: 2,
      unit_price_snapshot: '19.99',
      line_total: '39.98',
    },
  ],
  subtotal: '39.98',
  seller: { id: 7, name: 'Lola Beauty' },
}

export const emptyCart: Cart = { items: [], subtotal: '0.00', seller: null }

export const orders: OrderListItem[] = [
  { id: 5001, status: 'paid', currency: 'EUR', total: '44.97', placed_at: '2026-09-22T10:00:00Z' },
  {
    id: 5000,
    status: 'pending_payment',
    currency: 'EUR',
    total: '10.00',
    placed_at: '2026-09-21T10:00:00Z',
  },
]

export const orderDetail: OrderDetail = {
  id: 5001,
  status: 'paid',
  currency: 'EUR',
  subtotal: '39.98',
  shipping_cost: '4.99',
  total: '44.97',
  delivery_address: {
    street: 'Alexanderplatz 1',
    city: 'Berlin',
    postal_code: '10178',
    country: 'DE',
    phone: '+491234567',
    notes: null,
  },
  placed_at: '2026-09-22T10:00:00Z',
  items: [
    {
      id: 1,
      variant_id: 11,
      product_name_snapshot: 'Velvet Matte Lipstick',
      qty: 2,
      unit_price_snapshot: '19.99',
    },
  ],
  payment_status: 'succeeded',
  shipment_status: 'processing',
  refund_status: null,
  payment_method: 'stripe',
  reserved_until: '2026-09-22T10:15:00Z',
  cancel_reason: null,
}

export const courierProfile: CourierProfile = {
  id: 1,
  name: 'Ali',
  bot_username: 'shop_courier_bot',
  max_active_deliveries: 3,
}

export const poolItems: PoolItem[] = [
  {
    shipment_id: 501,
    order_id: 41,
    city: 'Berlin',
    street: 'Alexanderplatz 1',
    item_count: 2,
    placed_at: '2026-09-24T10:00:00Z',
    pickup: { name: 'Lola Beauty', address: 'Tashkent, Chilonzor 5', phone: '+998 90 111 22 33' },
  },
  {
    shipment_id: 502,
    order_id: 42,
    city: 'Berlin',
    street: 'Kastanienallee 5',
    item_count: 1,
    placed_at: '2026-09-24T10:05:00Z',
    pickup: { name: 'Lola Beauty', address: 'Tashkent, Chilonzor 5', phone: '+998 90 111 22 33' },
  },
]

export const assignedDelivery: CourierDelivery = {
  shipment_id: 501,
  order_id: 41,
  status: 'assigned',
  address: {
    street: 'Alexanderplatz 1',
    city: 'Berlin',
    postal_code: '10178',
    country: 'DE',
    phone: '+49 123 4567',
    notes: 'Ring twice',
  },
  destination: { latitude: 52.52, longitude: 13.405 },
  items: [{ name: 'Velvet Matte Lipstick', qty: 2 }],
  assigned_at: '2026-09-24T10:10:00Z',
  picked_up_at: null,
  pickup: { name: 'Lola Beauty', address: 'Tashkent, Chilonzor 5', phone: '+998 90 111 22 33' },
}

export const shippedDelivery: CourierDelivery = {
  ...assignedDelivery,
  shipment_id: 502,
  order_id: 42,
  status: 'shipped',
  address: { ...assignedDelivery.address, street: 'Kastanienallee 5', notes: null },
  destination: null,
  picked_up_at: '2026-09-24T10:20:00Z',
}

export const trackingProcessing: Tracking = {
  status: 'processing',
  courier: null,
  courier_location: null,
  destination: null,
  picked_up_at: null,
  delivered_at: null,
}

export const trackingAssigned: Tracking = {
  ...trackingProcessing,
  status: 'assigned',
  courier: { name: 'Ali' },
}

export const trackingShipped: Tracking = {
  ...trackingAssigned,
  status: 'shipped',
  courier_location: {
    latitude: 52.5,
    longitude: 13.4,
    updated_at: '2026-09-24T10:30:00Z',
    is_stale: false,
  },
  destination: { latitude: 52.52, longitude: 13.405 },
  picked_up_at: '2026-09-24T10:20:00Z',
}

export const trackingStale: Tracking = {
  ...trackingShipped,
  courier_location: { ...trackingShipped.courier_location!, is_stale: true },
}

export const trackingDelivered: Tracking = {
  ...trackingProcessing,
  status: 'delivered',
  destination: { latitude: 52.52, longitude: 13.405 },
  picked_up_at: '2026-09-24T10:20:00Z',
  delivered_at: '2026-09-24T10:50:00Z',
}
