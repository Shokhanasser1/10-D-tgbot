import { apiFetch } from '../../shared/api/client'
import type { Cart } from './types'

export function fetchCart(): Promise<Cart> {
  return apiFetch<Cart>('/cart/items')
}

export function addCartItem(variantId: number, qty: number): Promise<Cart> {
  return apiFetch<Cart>('/cart/items', {
    method: 'POST',
    body: { variant_id: variantId, qty },
  })
}

export function updateCartItem(itemId: number, qty: number): Promise<Cart> {
  return apiFetch<Cart>(`/cart/items/${itemId}`, { method: 'PATCH', body: { qty } })
}

export function removeCartItem(itemId: number): Promise<Cart> {
  return apiFetch<Cart>(`/cart/items/${itemId}`, { method: 'DELETE' })
}
