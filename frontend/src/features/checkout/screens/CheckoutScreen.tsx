import { Elements } from '@stripe/react-stripe-js'
import { loadStripe } from '@stripe/stripe-js'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import { ApiError } from '../../../shared/api/client'
import { requestWriteAccessIfNeeded } from '../../../shared/telegram/webApp'
import { formatClock } from '../../../shared/time/formatClock'
import type { DeliveryAddress } from '../../../shared/types'
import { PillButton } from '../../../shared/ui/PillButton'
import { Skeleton } from '../../../shared/ui/Skeleton'
import { useOrder } from '../../orders/hooks'
import {
  type CheckoutResponse,
  fetchPaymentMethods,
  type PaymentMethod,
  postCheckout,
} from '../api'
import { AddressForm } from '../components/AddressForm'
import { PaymentMethodPicker } from '../components/PaymentMethodPicker'
import { StripePaymentForm } from '../components/StripePaymentForm'
import { TelegramInvoiceStep } from '../components/TelegramInvoiceStep'
import styles from './CheckoutScreen.module.css'

// Only Stripe shops load Stripe's script (loadStripe fetches it on first call).
let stripePromise: ReturnType<typeof loadStripe> | undefined
function getStripe() {
  stripePromise ??= loadStripe(import.meta.env.VITE_STRIPE_PUBLISHABLE_KEY as string)
  return stripePromise
}

type Step =
  | { name: 'address' }
  | { name: 'stripe'; orderId: number; clientSecret: string; reservedUntil: string }
  | { name: 'telegram'; orderId: number; invoiceUrl: string; reservedUntil: string }
  | { name: 'confirming'; orderId: number }

function nextStep(response: CheckoutResponse): Step {
  if (response.payment_method === 'telegram' && response.invoice_url) {
    return {
      name: 'telegram',
      orderId: response.order_id,
      invoiceUrl: response.invoice_url,
      reservedUntil: response.reserved_until,
    }
  }
  if (response.payment_method === 'stripe' && response.client_secret) {
    return {
      name: 'stripe',
      orderId: response.order_id,
      clientSecret: response.client_secret,
      reservedUntil: response.reserved_until,
    }
  }
  // Cash on delivery: nothing to pay now, the order is already confirmed.
  return { name: 'confirming', orderId: response.order_id }
}

export function CheckoutScreen() {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [step, setStep] = useState<Step>({ name: 'address' })
  const methodsQuery = useQuery({ queryKey: ['payment-methods'], queryFn: fetchPaymentMethods })
  const methods = methodsQuery.data?.methods ?? []
  const [chosen, setChosen] = useState<PaymentMethod | undefined>()
  const method = chosen ?? methods[0]
  const noMethods = methodsQuery.isSuccess && methods.length === 0

  const checkoutMutation = useMutation({
    mutationFn: (address: DeliveryAddress) => postCheckout(address, method),
    onSuccess: (response) => {
      // Order updates are sent to the bot chat; Telegram asks the user once if needed.
      requestWriteAccessIfNeeded()
      setStep(nextStep(response))
    },
    onError: (error) => {
      if (isSoldOut(error)) {
        // Someone else bought the last units: show the cart and catalog as they are now.
        void queryClient.invalidateQueries({ queryKey: ['cart'] })
        void queryClient.invalidateQueries({ queryKey: ['products'] })
        void queryClient.invalidateQueries({ queryKey: ['product'] })
      }
    },
  })

  const confirmingOrderId = step.name === 'confirming' ? step.orderId : Number.NaN
  const orderQuery = useOrder(confirmingOrderId)

  useEffect(() => {
    if (
      step.name === 'confirming' &&
      orderQuery.data &&
      orderQuery.data.status !== 'pending_payment'
    ) {
      navigate(`/orders/${step.orderId}`, { replace: true })
    }
  }, [step, orderQuery.data, navigate])

  if (step.name === 'confirming') {
    return (
      <div className={styles.screen}>
        <p className={styles.status}>{t('checkout.confirming')}</p>
        <Skeleton height={80} radius="18px" />
      </div>
    )
  }

  if (step.name === 'stripe' || step.name === 'telegram') {
    const paid = () => setStep({ name: 'confirming', orderId: step.orderId })
    return (
      <div className={styles.screen}>
        <p className={styles.deadline}>
          {t('checkout.payBy', { time: formatClock(step.reservedUntil, i18n.language) })}
        </p>
        {step.name === 'telegram' ? (
          <TelegramInvoiceStep invoiceUrl={step.invoiceUrl} onPaid={paid} />
        ) : (
          <Elements stripe={getStripe()} options={{ clientSecret: step.clientSecret }}>
            <StripePaymentForm onPaid={paid} />
          </Elements>
        )}
      </div>
    )
  }

  return (
    <div className={styles.screen}>
      <h1 className={styles.title}>{t('checkout.title')}</h1>
      <AddressForm
        onSubmit={(address) => checkoutMutation.mutate(address)}
        isSubmitting={checkoutMutation.isPending || methodsQuery.isLoading || noMethods}
        submitLabel={method === 'cash' ? t('checkout.placeOrder') : undefined}
      >
        {method && <PaymentMethodPicker methods={methods} value={method} onChange={setChosen} />}
      </AddressForm>
      {noMethods && (
        <p className={styles.error} role="alert">
          {t('checkout.noMethods')}
        </p>
      )}
      {checkoutMutation.isError &&
        (isSoldOut(checkoutMutation.error) ? (
          <div className={styles.soldOut} role="alert">
            <p className={styles.error}>{t('checkout.soldOut')}</p>
            <PillButton variant="secondary" onClick={() => navigate('/cart')}>
              {t('checkout.backToCart')}
            </PillButton>
          </div>
        ) : (
          <p className={styles.error}>
            {errorCode(checkoutMutation.error) === 'payment_unavailable'
              ? t('checkout.paymentUnavailable')
              : t('common.error')}
          </p>
        ))}
    </div>
  )
}

function errorCode(error: unknown): string | undefined {
  if (!(error instanceof ApiError)) return undefined
  const detail = error.detail
  if (typeof detail === 'object' && detail !== null && 'code' in detail) {
    const { code } = detail as { code: unknown }
    return typeof code === 'string' ? code : undefined
  }
  return undefined
}

function isSoldOut(error: unknown): boolean {
  return errorCode(error) === 'insufficient_stock'
}
