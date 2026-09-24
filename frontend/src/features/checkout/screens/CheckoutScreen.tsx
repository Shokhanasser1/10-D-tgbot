import { Elements } from '@stripe/react-stripe-js'
import { loadStripe } from '@stripe/stripe-js'
import { useMutation } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import type { DeliveryAddress } from '../../../shared/types'
import { Skeleton } from '../../../shared/ui/Skeleton'
import { useOrder } from '../../orders/hooks'
import { postCheckout } from '../api'
import { AddressForm } from '../components/AddressForm'
import { StripePaymentForm } from '../components/StripePaymentForm'
import styles from './CheckoutScreen.module.css'

const stripePromise = loadStripe(import.meta.env.VITE_STRIPE_PUBLISHABLE_KEY as string)

type Step =
  | { name: 'address' }
  | { name: 'payment'; orderId: number; clientSecret: string }
  | { name: 'confirming'; orderId: number }

export function CheckoutScreen() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [step, setStep] = useState<Step>({ name: 'address' })

  const checkoutMutation = useMutation({
    mutationFn: (address: DeliveryAddress) => postCheckout(address),
    onSuccess: (response) => {
      setStep({
        name: 'payment',
        orderId: response.order_id,
        clientSecret: response.client_secret,
      })
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
      {checkoutMutation.isError && <p className={styles.error}>{t('common.error')}</p>}
    </div>
  )
}
