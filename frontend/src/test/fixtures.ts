import type { Cart } from '../features/cart/types'
import type { Category, ProductDetail, ProductListItem } from '../features/catalog/types'
import type { OrderDetail, OrderListItem } from '../features/orders/types'

export const categories: Category[] = [
  { id: 1, slug: 'lipstick', parent_id: null, sort_order: 0, name: 'Lipstick' },
  { id: 2, slug: 'serums', parent_id: null, sort_order: 1, name: 'Serums' },
]

export const products: ProductListItem[] = [
  {
    id: 1,
    category_id: 1,
    base_sku: 'LIP-VELVET',
    base_price: '19.99',
    name: 'Velvet Matte Lipstick',
    thumbnail_url: null,
  },
  {
    id: 2,
    category_id: 2,
    base_sku: 'SERUM-VITC',
    base_price: '24.50',
    name: 'Vitamin C Serum',
    thumbnail_url: null,
  },
]

export const productDetail: ProductDetail = {
  id: 1,
  category_id: 1,
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
}

export const emptyCart: Cart = { items: [], subtotal: '0.00' }

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
}
