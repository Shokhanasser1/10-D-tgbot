import type {
  Admin,
  AdminAttribute,
  AdminCategory,
  AdminCourier,
  AdminMe,
  AdminOrder,
  AdminOrderListItem,
  AdminProduct,
  AdminProductListItem,
  AdminRole,
  AdminSeller,
  AdminShipment,
  Ledger,
  Permission,
  SellerOrder,
  SellerOrderListItem,
  CourierLocation,
  Summary,
} from '../features/admin/types'

/** A copy of the API's role table (backend app/core/permissions.py), for tests only. */
export const PERMISSIONS_BY_ROLE: Record<AdminRole, Permission[]> = {
  owner: [
    'summary.view',
    'catalog.view',
    'catalog.edit',
    'orders.view',
    'orders.cancel_unpaid',
    'orders.cancel_paid',
    'refunds.manage',
    'couriers.view',
    'couriers.manage',
    'admins.manage',
    'taxonomy.edit',
    'sellers.manage',
    'orders.prepare',
    'payouts.manage',
  ],
  manager: [
    'summary.view',
    'catalog.view',
    'catalog.edit',
    'orders.view',
    'orders.cancel_unpaid',
    'orders.cancel_paid',
    'couriers.view',
    'couriers.manage',
    'taxonomy.edit',
    'sellers.manage',
    'orders.prepare',
  ],
  catalog_manager: ['catalog.view', 'catalog.edit', 'taxonomy.edit'],
  dispatcher: [
    'orders.view',
    'orders.cancel_unpaid',
    'orders.prepare',
    'couriers.view',
    'couriers.manage',
  ],
  accountant: [
    'summary.view',
    'orders.view',
    'orders.cancel_paid',
    'refunds.manage',
    'payouts.manage',
  ],
  viewer: ['summary.view', 'catalog.view', 'orders.view', 'couriers.view'],
  seller: ['catalog.view', 'catalog.edit', 'orders.prepare'],
}

export function adminMe(role: AdminRole = 'owner', overrides: Partial<AdminMe> = {}): AdminMe {
  return {
    telegram_id: 500,
    display_name: 'Dilnoza',
    role,
    permissions: PERMISSIONS_BY_ROLE[role],
    login: 'dilnoza',
    has_password: true,
    must_change_password: false,
    seller_id: role === 'seller' ? 7 : null,
    seller_name: role === 'seller' ? 'Lola Beauty' : null,
    ...overrides,
  }
}

export const adminCategories: AdminCategory[] = [
  {
    id: 1,
    slug: 'lipstick',
    parent_id: null,
    sort_order: 0,
    name: 'Lipstick',
    translations: { en: { name: 'Lipstick' }, ru: { name: 'Помада' } },
  },
  {
    id: 2,
    slug: 'serums',
    parent_id: null,
    sort_order: 1,
    name: 'Serums',
    translations: { en: { name: 'Serums' } },
  },
]

export const adminAttributes: AdminAttribute[] = [
  {
    id: 7,
    key: 'shade',
    category_id: 1,
    value_type: 'text',
    translations: { en: { name: 'Shade' } },
  },
]

export const adminProductList: AdminProductListItem[] = [
  {
    id: 1,
    category_id: 1,
    seller_id: 7,
    seller_name: 'Lola Beauty',
    base_sku: 'LIP-VELVET',
    base_price: '19.99',
    status: 'active',
    name: 'Velvet Matte Lipstick',
    thumbnail_url: '/media/products/abc.webp',
    variant_count: 2,
    min_price: '19.99',
    total_stock: 8,
  },
  {
    id: 2,
    category_id: 2,
    seller_id: 8,
    seller_name: 'Anor',
    base_sku: 'SERUM-VITC',
    base_price: '24.50',
    status: 'draft',
    name: 'Vitamin C Serum',
    thumbnail_url: null,
    variant_count: 0,
    min_price: null,
    total_stock: 0,
  },
]

export const adminProduct: AdminProduct = {
  id: 1,
  category_id: 1,
  seller_id: 7,
  seller_name: 'Lola Beauty',
  base_sku: 'LIP-VELVET',
  base_price: '19.99',
  status: 'active',
  name: 'Velvet Matte Lipstick',
  translations: {
    en: { name: 'Velvet Matte Lipstick', description: 'Long-lasting.' },
    ru: { name: 'Бархатная помада' },
  },
  variants: [
    {
      id: 11,
      product_id: 1,
      sku: 'LIP-VELVET-RED',
      price: '19.99',
      stock_qty: 5,
      attribute_values: { shade: 'Red' },
    },
  ],
  images: [
    { id: 31, product_id: 1, variant_id: null, url: '/media/products/b.webp', position: 1 },
    { id: 30, product_id: 1, variant_id: null, url: '/media/products/a.webp', position: 0 },
  ],
}

export const adminOrderList: AdminOrderListItem[] = [
  {
    id: 42,
    status: 'paid',
    currency: 'EUR',
    total: '34.97',
    placed_at: '2026-09-24T10:00:00Z',
    telegram_id: 900,
    customer_name: 'Aziza K',
    shipment_status: 'processing',
    stock_shortfall: true,
    refund_status: null,
    seller_id: 7,
    seller_name: 'Lola Beauty',
    ready_at: null,
  },
  {
    id: 41,
    status: 'cancelled',
    currency: 'EUR',
    total: '14.99',
    placed_at: '2026-09-23T10:00:00Z',
    telegram_id: 901,
    customer_name: null,
    shipment_status: 'cancelled',
    stock_shortfall: false,
    refund_status: 'failed',
    seller_id: 8,
    seller_name: 'Anor',
    ready_at: '2026-09-23T10:05:00Z',
  },
]

export function adminOrder(overrides: Partial<AdminOrder> = {}): AdminOrder {
  return {
    id: 42,
    status: 'paid',
    currency: 'EUR',
    subtotal: '29.98',
    shipping_cost: '4.99',
    total: '34.97',
    delivery_address: {
      street: 'Amir Temur 1',
      city: 'Tashkent',
      postal_code: '100000',
      country: 'UZ',
      phone: '+998901112233',
      notes: 'Call first',
      latitude: 41.3,
      longitude: 69.2,
    },
    placed_at: '2026-09-24T10:00:00Z',
    customer: { telegram_id: 900, first_name: 'Aziza', last_name: 'K', username: 'aziza' },
    items: [
      {
        id: 1,
        variant_id: 11,
        sku: 'LIP-VELVET-RED',
        product_id: 1,
        product_name_snapshot: 'Velvet Matte Lipstick',
        qty: 2,
        unit_price_snapshot: '14.99',
      },
    ],
    payment: { status: 'succeeded', amount: '34.97', refund_status: null },
    shipment: {
      id: 5,
      status: 'processing',
      courier_id: null,
      courier_name: null,
      assigned_at: null,
      picked_up_at: null,
      delivered_at: null,
      ready_at: '2026-09-24T10:05:00Z',
    },
    stock_shortfall: false,
    cancelled_at: null,
    cancelled_by: null,
    cancel_reason: null,
    can_cancel: true,
    seller: {
      id: 7,
      name: 'Lola Beauty',
      phone: '+998 90 555 66 77',
      pickup_address: 'Tashkent, Chilonzor 5',
    },
    can_mark_ready: false,
    ...overrides,
  }
}

export const adminCouriers: AdminCourier[] = [
  {
    id: 3,
    telegram_id: 222,
    name: 'Bekzod',
    phone: '+998900000000',
    is_active: true,
    active_deliveries: 2,
  },
  { id: 4, telegram_id: 223, name: 'Jasur', phone: null, is_active: false, active_deliveries: 0 },
]

export const adminShipments: AdminShipment[] = [
  {
    id: 5,
    order_id: 42,
    status: 'assigned',
    courier_id: 3,
    courier_name: 'Bekzod',
    assigned_at: '2026-09-24T11:00:00Z',
    picked_up_at: null,
  },
  {
    id: 6,
    order_id: 43,
    status: 'shipped',
    courier_id: 3,
    courier_name: 'Bekzod',
    assigned_at: '2026-09-24T11:00:00Z',
    picked_up_at: '2026-09-24T11:30:00Z',
  },
]

export const courierLocations: CourierLocation[] = [
  {
    courier_id: 3,
    name: 'Bekzod',
    latitude: 41.31,
    longitude: 69.24,
    updated_at: '2026-09-24T11:40:00Z',
    is_stale: true,
    active_deliveries: 2,
  },
]

export const summary: Summary = {
  period: 'today',
  currency: 'EUR',
  revenue: '104.91',
  orders_count: 3,
  average_order: '34.97',
  status_counts: {
    pending_payment: 1,
    paid: 2,
    processing: 1,
    shipped: 0,
    delivered: 5,
    cancelled: 1,
  },
  low_stock: [
    {
      variant_id: 11,
      product_id: 1,
      sku: 'LIP-VELVET-RED',
      name: 'Velvet Matte Lipstick',
      stock_qty: 0,
    },
  ],
  top_products: [{ product_id: 1, name: 'Velvet Matte Lipstick', qty: 4, revenue: '59.96' }],
}

export const admins: Admin[] = [
  {
    id: 1,
    telegram_id: 500,
    role: 'owner',
    display_name: 'Dilnoza',
    is_active: true,
    created_at: '2026-09-01T00:00:00Z',
    created_by: null,
  },
  {
    id: 2,
    telegram_id: 501,
    role: 'dispatcher',
    display_name: 'Jasur',
    is_active: true,
    created_at: '2026-09-02T00:00:00Z',
    created_by: 500,
  },
]

export const adminSellers: AdminSeller[] = [
  {
    id: 7,
    name: 'Lola Beauty',
    phone: '+998901112233',
    pickup_address: 'Tashkent, Chilonzor 5',
    is_active: true,
    accounts: [{ id: 3, telegram_id: 502, display_name: 'Lola', is_active: true }],
    product_count: 1,
    commission_percent: '10.00',
    balances: [{ currency: 'EUR', earned: '27.00', paid_out: '0.00', balance: '27.00' }],
  },
  {
    id: 8,
    name: 'Anor',
    phone: null,
    pickup_address: 'Yunusobod 1',
    is_active: false,
    accounts: [],
    product_count: 0,
    commission_percent: '12.50',
    balances: [],
  },
]

export const sellerOrderList: SellerOrderListItem[] = [
  {
    id: 42,
    status: 'paid',
    placed_at: '2026-09-24T10:00:00Z',
    subtotal: '29.98',
    currency: 'EUR',
    payment_method: 'cash',
    item_count: 2,
    shipment_status: 'processing',
    ready_at: null,
  },
  {
    id: 40,
    status: 'paid',
    placed_at: '2026-09-23T10:00:00Z',
    subtotal: '14.99',
    currency: 'EUR',
    payment_method: 'telegram',
    item_count: 1,
    shipment_status: 'processing',
    ready_at: '2026-09-23T10:30:00Z',
  },
]

export function sellerOrder(overrides: Partial<SellerOrder> = {}): SellerOrder {
  return {
    ...sellerOrderList[0],
    items: [
      {
        product_name: 'Velvet Matte Lipstick',
        sku: 'LIP-VELVET-RED',
        qty: 2,
        unit_price: '14.99',
        line_total: '29.98',
      },
    ],
    ...overrides,
  }
}

export const sellerLedger: Ledger = {
  balances: [{ currency: 'EUR', earned: '54.00', paid_out: '20.00', balance: '34.00' }],
  earnings: [
    {
      order_id: 43,
      earned_at: '2026-09-25T12:00:00Z',
      currency: 'EUR',
      goods_total: '30.00',
      commission_percent: '10.00',
      commission: '3.00',
      amount: '27.00',
    },
    {
      order_id: 42,
      earned_at: '2026-09-24T12:00:00Z',
      currency: 'EUR',
      goods_total: '30.00',
      commission_percent: '10.00',
      commission: '3.00',
      amount: '27.00',
    },
  ],
  payouts: [
    {
      id: 1,
      created_at: '2026-09-26T09:00:00Z',
      currency: 'EUR',
      amount: '20.00',
      note: 'Card *1234',
    },
  ],
}
