import { ApiError, apiFetch } from '../../shared/api/client'
import type { Cart } from './types'

export function fetchCart(): Promise<Cart> {
  return apiFetch<Cart>('/cart/items')
}

/** `replaceCart` empties a cart of another seller first, once the customer agreed (Spec 9). */
export function addCartItem(variantId: number, qty: number, replaceCart = false): Promise<Cart> {
  return apiFetch<Cart>('/cart/items', {
    method: 'POST',
    body: replaceCart
      ? { variant_id: variantId, qty, replace_cart: true }
      : { variant_id: variantId, qty },
  })
}

/** The cart holds another seller's products: a cart holds one seller at a time. */
export function isOtherSellerConflict(error: unknown): boolean {
  if (!(error instanceof ApiError) || error.status !== 409) return false
  const detail = error.detail
  return (
    typeof detail === 'object' &&
    detail !== null &&
    (detail as { code?: unknown }).code === 'cart_other_seller'
  )
}

export function updateCartItem(itemId: number, qty: number): Promise<Cart> {
  return apiFetch<Cart>(`/cart/items/${itemId}`, { method: 'PATCH', body: { qty } })
}

export function removeCartItem(itemId: number): Promise<Cart> {
  return apiFetch<Cart>(`/cart/items/${itemId}`, { method: 'DELETE' })
}
