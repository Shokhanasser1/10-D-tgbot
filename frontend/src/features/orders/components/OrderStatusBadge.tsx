import { useTranslation } from 'react-i18next'

import type { OrderStatus } from '../types'
import styles from './OrderStatusBadge.module.css'

const POSITIVE_STATUSES: OrderStatus[] = ['paid', 'processing', 'shipped', 'delivered']

function variantFor(status: OrderStatus): string {
  if (status === 'cancelled') return styles.negative
  if (POSITIVE_STATUSES.includes(status)) return styles.positive
  return styles.neutral
}

interface OrderStatusBadgeProps {
  status: OrderStatus
}

export function OrderStatusBadge({ status }: OrderStatusBadgeProps) {
  const { t } = useTranslation()

  return (
    <span className={[styles.badge, variantFor(status)].join(' ')}>
      {t(`orders.status.${status}`)}
    </span>
  )
}
