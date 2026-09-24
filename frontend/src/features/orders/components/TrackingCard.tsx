import { useTranslation } from 'react-i18next'

import { LazyTrackingMap } from '../../../shared/map/LazyTrackingMap'
import { formatAgo, secondsSince } from '../../../shared/time/formatAgo'
import { useNow } from '../../../shared/time/useNow'
import { Card } from '../../../shared/ui/Card'
import { PillButton } from '../../../shared/ui/PillButton'
import { Skeleton } from '../../../shared/ui/Skeleton'
import { isTrackedOrder, useTracking } from '../hooks'
import type { OrderStatus, Tracking } from '../types'
import styles from './TrackingCard.module.css'
import { TrackingTimeline } from './TrackingTimeline'

interface TrackingCardProps {
  orderId: number
  orderStatus: OrderStatus
}

function StatusLine({ tracking, now }: { tracking: Tracking; now: number }) {
  const { t } = useTranslation()
  const name = tracking.courier?.name ?? ''

  switch (tracking.status) {
    case 'assigned':
      return <p className={styles.line}>{t('tracking.courierAssigned', { name })}</p>
    case 'shipped':
      return (
        <p className={styles.line}>
          {t(tracking.courier_location ? 'tracking.onTheWay' : 'tracking.waitingForLocation', {
            name,
          })}
        </p>
      )
    case 'delivered':
      return (
        <p className={styles.line}>
          {tracking.delivered_at
            ? t('tracking.deliveredAt', {
                ago: formatAgo(t, secondsSince(tracking.delivered_at, now)),
              })
            : t('tracking.delivered')}
        </p>
      )
    default:
      return <p className={styles.line}>{t('tracking.waitingForCourier')}</p>
  }
}

/**
 * Where a customer's order is, in words and, once a courier is out with it, on a map. A failure
 * here never takes the rest of the order page down with it.
 */
export function TrackingCard({ orderId, orderStatus }: TrackingCardProps) {
  const { t } = useTranslation()
  const query = useTracking(orderId, orderStatus)
  const now = useNow(15_000)

  if (!isTrackedOrder(orderStatus)) return null
  if (query.isLoading) return <Skeleton height={140} radius="18px" />

  const tracking = query.data
  if (!tracking) {
    return (
      <Card className={styles.card}>
        <p className={styles.line}>{t('tracking.loadFailed')}</p>
        <PillButton variant="secondary" onClick={() => query.refetch()}>
          {t('common.retry')}
        </PillButton>
      </Card>
    )
  }

  const location = tracking.courier_location
  const showMap = tracking.status !== 'delivered' && (location !== null || tracking.destination)

  return (
    <Card className={styles.card}>
      <h2 className={styles.title}>{t('tracking.title')}</h2>
      <TrackingTimeline status={tracking.status} />
      <StatusLine tracking={tracking} now={now} />

      {location?.is_stale && (
        <p role="status" className={styles.stale}>
          {t('tracking.staleBanner', {
            ago: formatAgo(t, secondsSince(location.updated_at, now)),
          })}
        </p>
      )}

      {showMap && (
        <LazyTrackingMap
          label={t('tracking.mapLabel')}
          destination={tracking.destination}
          courier={
            location
              ? {
                  latitude: location.latitude,
                  longitude: location.longitude,
                  isStale: location.is_stale,
                }
              : null
          }
        />
      )}
    </Card>
  )
}
