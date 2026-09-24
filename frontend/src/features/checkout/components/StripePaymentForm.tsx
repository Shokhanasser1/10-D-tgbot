import { PaymentElement, useElements, useStripe } from '@stripe/react-stripe-js'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { useMainButton } from '../../../shared/telegram/hooks'
import { ActionBar } from '../../../shared/ui/ActionBar'
import styles from './StripePaymentForm.module.css'

interface StripePaymentFormProps {
  onPaid: () => void
}

export function StripePaymentForm({ onPaid }: StripePaymentFormProps) {
  const { t } = useTranslation()
  const stripe = useStripe()
  const elements = useElements()
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleConfirm() {
    if (!stripe || !elements || isSubmitting) return
    setIsSubmitting(true)
    setError(null)

    const { error: confirmError } = await stripe.confirmPayment({
      elements,
      redirect: 'if_required',
    })

    if (confirmError) {
      setError(confirmError.message ?? t('common.error'))
      setIsSubmitting(false)
      return
    }

    onPaid()
  }

  const label = isSubmitting ? t('checkout.processing') : t('checkout.submit')
  const disabled = !stripe || isSubmitting

  useMainButton({
    text: label,
    onClick: handleConfirm,
    visible: true,
    enabled: !disabled,
  })

  return (
    <div className={styles.form}>
      <PaymentElement />
      {error && <p className={styles.error}>{error}</p>}
      <ActionBar label={label} onClick={handleConfirm} disabled={disabled} />
    </div>
  )
}
