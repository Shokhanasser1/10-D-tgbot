import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Navigate, useSearchParams } from 'react-router-dom'

import { EmptyState } from '../../../shared/ui/EmptyState'
import { QueryError } from '../../../shared/ui/QueryError'
import { Skeleton } from '../../../shared/ui/Skeleton'
import { CourierTabs } from '../components/CourierTabs'
import { DeliveryCard } from '../components/DeliveryCard'
import { GpsPanel } from '../components/GpsPanel'
import { PoolCard } from '../components/PoolCard'
import { courierErrorKey, isForbidden } from '../errors'
import {
  courierKeys,
  useCourierActions,
  useCourierDeliveries,
  useCourierPool,
  useCourierProfile,
} from '../hooks'
import type { CourierTab } from '../types'
import styles from './CourierScreen.module.css'

export function CourierScreen() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const tab: CourierTab = searchParams.get('tab') === 'mine' ? 'mine' : 'pool'
  const [actionError, setActionError] = useState<string | null>(null)

  const profileQuery = useCourierProfile()
  const profile = profileQuery.data
  const isCourier = !!profile
  const poolQuery = useCourierPool(isCourier)
  const deliveriesQuery = useCourierDeliveries(isCourier)
  const actions = useCourierActions()

  // The owner can deactivate a courier while the app is open; every courier endpoint then
  // answers 403. Forget the profile so the shell hides the entry point and this screen leaves.
  const deactivated = isForbidden(poolQuery.error) || isForbidden(deliveriesQuery.error)
  useEffect(() => {
    if (deactivated) queryClient.setQueryData(courierKeys.profile, null)
  }, [deactivated, queryClient])

  if (profileQuery.isLoading) {
    return (
      <div className={styles.screen}>
        <Skeleton height={44} radius="999px" />
        <Skeleton height={120} />
      </div>
    )
  }
  if (profileQuery.isError) return <QueryError onRetry={() => profileQuery.refetch()} />
  if (!profile || deactivated) return <Navigate to="/" replace />

  const deliveries = deliveriesQuery.data?.deliveries ?? []
  const pool = poolQuery.data ?? []

  function run(mutation: { mutate: (id: number, options: object) => void }, shipmentId: number) {
    setActionError(null)
    mutation.mutate(shipmentId, {
      onError: (error: unknown) => {
        if (isForbidden(error)) queryClient.setQueryData(courierKeys.profile, null)
        else setActionError(t(courierErrorKey(error)))
      },
    })
  }

  const busyId = actions.busyShipmentId

  return (
    <div className={styles.screen}>
      <h1 className={styles.title}>{t('courier.title')}</h1>
      <CourierTabs
        tab={tab}
        onChange={(next) => setSearchParams({ tab: next }, { replace: true })}
        poolCount={poolQuery.data ? pool.length : null}
        mineCount={deliveriesQuery.data ? deliveries.length : null}
      />
      <p className={styles.capacity}>
        {t('courier.capacity', { current: deliveries.length, max: profile.max_active_deliveries })}
      </p>
      {actionError && (
        <p role="alert" className={styles.error}>
          {actionError}
        </p>
      )}

      {tab === 'pool' && (
        <section className={styles.list}>
          {poolQuery.isError && !poolQuery.data && (
            <QueryError onRetry={() => poolQuery.refetch()} />
          )}
          {poolQuery.isLoading && <Skeleton height={140} />}
          {poolQuery.data && pool.length === 0 && (
            <EmptyState
              title={t('courier.pool.empty')}
              description={t('courier.pool.emptyDescription')}
            />
          )}
          {pool.map((item) => (
            <PoolCard
              key={item.shipment_id}
              item={item}
              isBusy={busyId === item.shipment_id}
              onClaim={(id) => run(actions.claim, id)}
            />
          ))}
        </section>
      )}

      {tab === 'mine' && (
        <section className={styles.list}>
          {deliveriesQuery.isError && !deliveriesQuery.data && (
            <QueryError onRetry={() => deliveriesQuery.refetch()} />
          )}
          {deliveriesQuery.isLoading && <Skeleton height={200} />}
          {deliveriesQuery.data && deliveries.length === 0 && (
            <EmptyState
              title={t('courier.mine.empty')}
              description={t('courier.mine.emptyDescription')}
            />
          )}
          {deliveries.length > 0 && (
            <GpsPanel
              botUsername={profile.bot_username}
              locationUpdatedAt={deliveriesQuery.data?.location_updated_at ?? null}
            />
          )}
          {deliveries.map((delivery) => (
            <DeliveryCard
              key={delivery.shipment_id}
              delivery={delivery}
              isBusy={busyId === delivery.shipment_id}
              onPickup={(id) => run(actions.pickup, id)}
              onDeliver={(id) => run(actions.deliver, id)}
              onRelease={(id) => run(actions.release, id)}
            />
          ))}
        </section>
      )}
    </div>
  )
}
