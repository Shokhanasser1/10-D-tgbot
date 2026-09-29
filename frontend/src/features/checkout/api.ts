import { apiFetch } from '../../shared/api/client'
import type { DeliveryAddress } from '../../shared/types'

export type PaymentMethod = 'telegram' | 'cash' | 'stripe'

export interface PaymentMethods {
  /** The methods the shop has switched on, in the order to offer them. */
  methods: PaymentMethod[]
  currency: string
}

export interface CheckoutResponse {
  order_id: number
  payment_method: PaymentMethod
  /** Stripe: confirm the PaymentIntent with this. */
  client_secret: string | null
  /** Telegram Payments (Click/Payme): open this invoice. */
  invoice_url: string | null
  total: string
  currency: string
  /** Pay before this or the order expires and the items go back to the cart. */
  reserved_until: string
}

export function fetchPaymentMethods(): Promise<PaymentMethods> {
  return apiFetch<PaymentMethods>('/checkout/methods')
}

export function postCheckout(
  address: DeliveryAddress,
  paymentMethod?: PaymentMethod,
): Promise<CheckoutResponse> {
  return apiFetch<CheckoutResponse>('/checkout', {
    method: 'POST',
    body: { delivery_address: address, payment_method: paymentMethod },
  })
}
