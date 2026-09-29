import { apiFetch } from '../../shared/api/client'
import type { DeliveryAddress } from '../../shared/types'

export interface CheckoutResponse {
  order_id: number
  client_secret: string
  total: string
  currency: string
  /** Pay before this or the order expires and the items go back to the cart. */
  reserved_until: string
}

export function postCheckout(address: DeliveryAddress): Promise<CheckoutResponse> {
  return apiFetch<CheckoutResponse>('/checkout', {
    method: 'POST',
    body: { delivery_address: address },
  })
}
