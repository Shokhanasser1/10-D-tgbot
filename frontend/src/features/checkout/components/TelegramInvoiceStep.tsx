import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { openInvoice } from '../../../shared/telegram/webApp'
import { PillButton } from '../../../shared/ui/PillButton'
import styles from './TelegramInvoiceStep.module.css'

interface TelegramInvoiceStepProps {
  invoiceUrl: string
  onPaid: () => void
}

/**
 * Telegram's own payment sheet (Click/Payme) opens over the app. If the customer closes it,
 * they can open it again while the order is still held.
 */
export function TelegramInvoiceStep({ invoiceUrl, onPaid }: TelegramInvoiceStepProps) {
  const { t } = useTranslation()
  const [state, setState] = useState<'open' | 'closed' | 'failed'>('open')
  const opened = useRef(false)

  const open = () => {
    setState('open')
    openInvoice(invoiceUrl, (status) => {
      if (status === 'paid' || status === 'pending') onPaid()
      else setState(status === 'failed' ? 'failed' : 'closed')
    })
  }

  useEffect(() => {
    // Once per mount, including React's development double-invocation of effects.
    if (opened.current) return
    opened.current = true
    open()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div className={styles.step}>
      {state === 'failed' && (
        <p className={styles.error} role="alert">
          {t('checkout.invoiceFailed')}
        </p>
      )}
      {state === 'closed' && <p className={styles.text}>{t('checkout.invoiceClosed')}</p>}
      <PillButton onClick={open}>{t('checkout.payWithTelegram')}</PillButton>
    </div>
  )
}
