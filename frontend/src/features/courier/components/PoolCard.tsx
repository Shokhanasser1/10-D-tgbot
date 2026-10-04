import { useTranslation } from 'react-i18next'

import { formatMoney } from '../../../shared/money/formatMoney'
import { Card } from '../../../shared/ui/Card'
import { PillButton } from '../../../shared/ui/PillButton'
import { formatAgo, secondsSince } from '../../../shared/time/formatAgo'
import { useNow } from '../../../shared/time/useNow'
import type { PoolItem } from '../types'
import { pickupPlace } from './pickup'
import styles from './PoolCard.module.css'

interface PoolCardProps {
  item: PoolItem
  isBusy: boolean
  onClaim: (shipmentId: number) => void
}

export function PoolCard({ item, isBusy, onClaim }: PoolCardProps) {
  const { t, i18n } = useTranslation()
  const now = useNow(15_000)

  return (
    <Card className={styles.card}>
      <div className={styles.header}>
        <span className={styles.orderId}>#{item.order_id}</span>
        <span className={styles.meta}>
          {t('courier.pool.placed', { ago: formatAgo(t, secondsSince(item.placed_at, now)) })}
        </span>
      </div>
      <p className={styles.address}>
        {item.street}, {item.city}
      </p>
      <p className={styles.meta}>{t('courier.pool.items', { count: item.item_count })}</p>
      <p className={styles.meta}>{t('courier.pickup', { place: pickupPlace(item.pickup) })}</p>
      {item.cash_to_collect && (
        <p className={styles.meta}>
          {t('courier.cash', {
            total: formatMoney(item.cash_to_collect, item.currency ?? 'UZS', i18n.language),
          })}
        </p>
      )}
      <PillButton
        className={styles.action}
        disabled={isBusy}
        onClick={() => onClaim(item.shipment_id)}
      >
        {t('courier.pool.claim')}
      </PillButton>
    </Card>
  )
}
