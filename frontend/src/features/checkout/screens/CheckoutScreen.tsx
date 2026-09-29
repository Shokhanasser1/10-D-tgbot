import { Elements } from '@stripe/react-stripe-js'
import { loadStripe } from '@stripe/stripe-js'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import { ApiError } from '../../../shared/api/client'
import { formatClock } from '../../../shared/time/formatClock'
import type { DeliveryAddress } from '../../../shared/types'
import { PillButton } from '../../../shared/ui/PillButton'
import { Skeleton } from '../../../shared/ui/Skeleton'
import { useOrder } from '../../orders/hooks'
import { postCheckout } from '../api'
import { AddressForm } from '../components/AddressForm'
import { StripePaymentForm } from '../components/StripePaymentForm'
import styles from './CheckoutScreen.module.css'

const stripePromise = loadStripe(import.meta.env.VITE_STRIPE_PUBLISHABLE_KEY as string)

type Step =
  | { name: 'address' }
  | { name: 'payment'; orderId: number; clientSecret: string; reservedUntil: string }
  | { name: 'confirming'; orderId: number }

export function CheckoutScreen() {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [step, setStep] = useState<Step>({ name: 'address' })

  const checkoutMutation = useMutation({
    mutationFn: (address: DeliveryAddress) => postCheckout(address),
    onSuccess: (response) => {
      setStep({
        name: 'payment',
        orderId: response.order_id,
        clientSecret: response.client_secret,
        reservedUntil: response.reserved_until,
      })
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

  if (step.name === 'payment') {
    return (
      <div className={styles.screen}>
        <p className={styles.deadline}>
          {t('checkout.payBy', { time: formatClock(step.reservedUntil, i18n.language) })}
        </p>
        <Elements stripe={stripePromise} options={{ clientSecret: step.clientSecret }}>
          <StripePaymentForm
            onPaid={() => setStep({ name: 'confirming', orderId: step.orderId })}
          />
        </Elements>
      </div>
    )
  }

  return (
    <div className={styles.screen}>
      <h1 className={styles.title}>{t('checkout.title')}</h1>
      <AddressForm
        onSubmit={(address) => checkoutMutation.mutate(address)}
        isSubmitting={checkoutMutation.isPending}
      />
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
