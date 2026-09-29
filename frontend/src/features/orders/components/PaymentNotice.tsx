import { useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import { formatClock } from '../../../shared/time/formatClock'
import { Card } from '../../../shared/ui/Card'
import { PillButton } from '../../../shared/ui/PillButton'
import type { OrderDetail } from '../types'
import styles from './PaymentNotice.module.css'

const RETURNED_TO_CART: Record<string, string> = {
  payment_expired: 'orders.reservation.expired',
  payment_setup_failed: 'orders.reservation.setupFailed',
}

/**
 * What happens to the customer's money and items outside the normal flow: the payment
 * deadline of an unpaid order, items returned to the cart, and refunds.
 */
export function PaymentNotice({ order }: { order: OrderDetail }) {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const lines: string[] = []
  if (order.status === 'pending_payment' && order.reserved_until) {
    lines.push(
      t('orders.reservation.pending', { time: formatClock(order.reserved_until, i18n.language) }),
    )
  }
  const returnedKey =
    order.status === 'cancelled' && order.cancel_reason
      ? RETURNED_TO_CART[order.cancel_reason]
      : undefined
  if (returnedKey) lines.push(t(returnedKey))
  if (order.refund_status) lines.push(t(`orders.refund.${order.refund_status}`))

  if (lines.length === 0) return null

  const openCart = () => {
    // The server put the items back; the cached cart does not know yet.
    void queryClient.invalidateQueries({ queryKey: ['cart'] })
    navigate('/cart')
  }

  return (
    <Card className={styles.notice} role="status">
      {lines.map((line) => (
        <p key={line} className={styles.text}>
          {line}
        </p>
      ))}
      {returnedKey && (
        <PillButton onClick={openCart}>{t('orders.reservation.openCart')}</PillButton>
      )}
    </Card>
  )
}
