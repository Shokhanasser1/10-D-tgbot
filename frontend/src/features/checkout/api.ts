import { apiFetch } from '../../shared/api/client'
import type { DeliveryAddress } from '../../shared/types'

export interface CheckoutResponse {
  order_id: number
  client_secret: string
  total: string
  currency: string
}

export function postCheckout(address: DeliveryAddress): Promise<CheckoutResponse> {
  return apiFetch<CheckoutResponse>('/checkout', {
    method: 'POST',
    body: { delivery_address: address },
  })
}
