import { type ApiFetchOptions, apiFetch } from '../../shared/api/client'
import type {
  Admin,
  AdminAttribute,
  AdminCategory,
  AdminCourier,
  AdminImage,
  AdminMe,
  AdminOrder,
  AdminOrderListItem,
  AdminProduct,
  AdminProductListItem,
  AdminRole,
  AdminShipment,
  AdminVariant,
  AttributeValueType,
  CourierLocation,
  OrderFilters,
  Page,
  ProductInput,
  ProductStatus,
  StatsPeriod,
  Summary,
  TelegramLoginData,
  TranslationInput,
  VariantInput,
} from './types'

function admin<T>(path: string, options: Omit<ApiFetchOptions, 'admin'> = {}): Promise<T> {
  return apiFetch<T>(`/internal${path}`, { ...options, admin: true })
}

// --- identity --------------------------------------------------------------------------------

export const fetchMe = () => admin<AdminMe>('/me')
export const loginWithTelegram = (data: TelegramLoginData) =>
  admin<AdminMe>('/auth/telegram', { method: 'POST', body: data })
export const logout = () => admin<void>('/auth/logout', { method: 'POST' })

export const fetchAdmins = () => admin<Admin[]>('/admins')
export const createAdmin = (body: { telegram_id: number; role: AdminRole; display_name: string }) =>
  admin<Admin>('/admins', { method: 'POST', body })
export const updateAdmin = (
  id: number,
  body: Partial<Pick<Admin, 'role' | 'display_name' | 'is_active'>>,
) => admin<Admin>(`/admins/${id}`, { method: 'PATCH', body })

// --- catalog ---------------------------------------------------------------------------------

export const fetchCategories = (locale: string) =>
  admin<AdminCategory[]>('/categories', { params: { locale } })
export const createCategory = (body: { slug: string; sort_order: number }) =>
  admin<AdminCategory>('/categories', { method: 'POST', body })
export const updateCategory = (id: number, body: { slug?: string; sort_order?: number }) =>
  admin<AdminCategory>(`/categories/${id}`, { method: 'PATCH', body })

export const fetchAttributes = () => admin<AdminAttribute[]>('/attributes')
export const createAttribute = (body: {
  key: string
  category_id: number
  value_type: AttributeValueType
}) => admin<AdminAttribute>('/attributes', { method: 'POST', body })
export const updateAttribute = (
  id: number,
  body: { key?: string; value_type?: AttributeValueType },
) => admin<AdminAttribute>(`/attributes/${id}`, { method: 'PATCH', body })

export interface ProductFilters {
  status?: ProductStatus
  category_id?: number
  q?: string
  offset?: number
}

export const PRODUCTS_PAGE_SIZE = 50

export const fetchProducts = (filters: ProductFilters, locale: string) =>
  admin<Page<AdminProductListItem>>('/products', {
    params: { ...filters, q: filters.q || undefined, limit: PRODUCTS_PAGE_SIZE, locale },
  })
export const fetchProduct = (id: number, locale: string) =>
  admin<AdminProduct>(`/products/${id}`, { params: { locale } })
export const createProduct = (body: ProductInput) =>
  admin<AdminProduct>('/products', { method: 'POST', body })
export const updateProduct = (id: number, body: Partial<ProductInput>) =>
  admin<AdminProduct>(`/products/${id}`, { method: 'PATCH', body })

export const createVariant = (productId: number, body: VariantInput) =>
  admin<AdminVariant>('/variants', { method: 'POST', body: { ...body, product_id: productId } })
export const updateVariant = (id: number, body: Partial<VariantInput>) =>
  admin<AdminVariant>(`/variants/${id}`, { method: 'PATCH', body })

export const upsertTranslation = (body: TranslationInput) =>
  admin<unknown>('/translations', { method: 'POST', body })

export function uploadImage(productId: number, file: File, position: number): Promise<AdminImage> {
  const form = new FormData()
  form.append('file', file)
  form.append('position', String(position))
  return admin<AdminImage>(`/products/${productId}/images`, { method: 'POST', body: form })
}
export const updateImage = (id: number, body: { position?: number; variant_id?: number | null }) =>
  admin<AdminImage>(`/images/${id}`, { method: 'PATCH', body })
export const deleteImage = (id: number) => admin<void>(`/images/${id}`, { method: 'DELETE' })

// --- orders ----------------------------------------------------------------------------------

export const ORDERS_PAGE_SIZE = 50

export const fetchOrders = (filters: OrderFilters) =>
  admin<Page<AdminOrderListItem>>('/orders', {
    params: { ...filters, q: filters.q || undefined, limit: ORDERS_PAGE_SIZE },
  })
export const fetchOrder = (id: number) => admin<AdminOrder>(`/orders/${id}`)
export const cancelOrder = (id: number, reason: string) =>
  admin<AdminOrder>(`/orders/${id}/cancel`, { method: 'POST', body: { reason } })
export const retryRefund = (id: number) =>
  admin<AdminOrder>(`/orders/${id}/refund`, { method: 'POST' })
/** An owner refunded a Click/Payme payment in the provider's cabinet. */
export const confirmManualRefund = (id: number) =>
  admin<AdminOrder>(`/orders/${id}/refund/confirm`, { method: 'POST' })

// --- couriers --------------------------------------------------------------------------------

export const fetchCouriers = () => admin<AdminCourier[]>('/couriers')
export const createCourier = (body: { telegram_id: number; name: string; phone: string | null }) =>
  admin<AdminCourier>('/couriers', { method: 'POST', body })
export const updateCourier = (
  id: number,
  body: { name?: string; phone?: string | null; is_active?: boolean },
) => admin<AdminCourier>(`/couriers/${id}`, { method: 'PATCH', body })
export const fetchShipments = () => admin<AdminShipment[]>('/shipments')
export const forceRelease = (shipmentId: number) =>
  admin<unknown>(`/shipments/${shipmentId}/release`, { method: 'POST' })
export const fetchCourierLocations = () => admin<CourierLocation[]>('/couriers/locations')

// --- summary ---------------------------------------------------------------------------------

export const fetchSummary = (period: StatsPeriod) =>
  admin<Summary>('/stats/summary', { params: { period } })
