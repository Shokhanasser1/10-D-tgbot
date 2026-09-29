import { type FormEvent, lazy, Suspense, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router-dom'

import { Card } from '../../../shared/ui/Card'
import { EmptyState } from '../../../shared/ui/EmptyState'
import { PillButton } from '../../../shared/ui/PillButton'
import { QueryError } from '../../../shared/ui/QueryError'
import { Skeleton } from '../../../shared/ui/Skeleton'
import { createCourier, forceRelease, updateCourier } from '../api'
import { Badge, ConfirmDialog, ErrorNote, Field, PageHeader } from '../components/ui'
import { adminErrorKey } from '../errors'
import { formatDateTime } from '../format'
import {
  useAdminCouriers,
  useAdminShipments,
  useCourierLocations,
  useDispatchMutation,
} from '../hooks'
import type { AdminCourier, AdminShipment } from '../types'
import { inputClass } from '../components/inputClass'
import styles from './CouriersScreen.module.css'
import { EditGate } from '../components/EditGate'

const CouriersMap = lazy(() =>
  import('../components/CouriersMap').then((module) => ({ default: module.CouriersMap })),
)

type Tab = 'couriers' | 'deliveries' | 'map'
const TABS: Tab[] = ['couriers', 'deliveries', 'map']

function AddCourierForm() {
  const { t } = useTranslation()
  const [form, setForm] = useState({ telegramId: '', name: '', phone: '' })
  const add = useDispatchMutation(createCourier)

  function submit(event: FormEvent) {
    event.preventDefault()
    add.mutate(
      {
        telegram_id: Number(form.telegramId),
        name: form.name.trim(),
        phone: form.phone.trim() || null,
      },
      { onSuccess: () => setForm({ telegramId: '', name: '', phone: '' }) },
    )
  }

  return (
    <form className={styles.form} onSubmit={submit}>
      <h2 className={styles.cardTitle}>{t('admin.couriers.add')}</h2>
      <div className={styles.grid}>
        <Field label={t('admin.common.telegramId')} hint={t('admin.common.telegramIdHint')}>
          {(id) => (
            <input
              id={id}
              required
              inputMode="numeric"
              pattern="[0-9]+"
              className={inputClass}
              value={form.telegramId}
              onChange={(event) => setForm({ ...form, telegramId: event.target.value })}
            />
          )}
        </Field>
        <Field label={t('admin.couriers.name')} hint={t('admin.couriers.nameHint')}>
          {(id) => (
            <input
              id={id}
              required
              maxLength={100}
              className={inputClass}
              value={form.name}
              onChange={(event) => setForm({ ...form, name: event.target.value })}
            />
          )}
        </Field>
        <Field label={t('admin.couriers.phone')}>
          {(id) => (
            <input
              id={id}
              type="tel"
              maxLength={32}
              className={inputClass}
              value={form.phone}
              onChange={(event) => setForm({ ...form, phone: event.target.value })}
            />
          )}
        </Field>
      </div>
      <ErrorNote message={add.error ? t(adminErrorKey(add.error)) : null} />
      <div className={styles.formActions}>
        <PillButton type="submit" disabled={add.isPending}>
          {t('admin.common.add')}
        </PillButton>
      </div>
    </form>
  )
}

function CouriersTab() {
  const { t } = useTranslation()
  const query = useAdminCouriers()
  const [toDeactivate, setToDeactivate] = useState<AdminCourier | null>(null)
  const toggle = useDispatchMutation(({ id, active }: { id: number; active: boolean }) =>
    updateCourier(id, { is_active: active }),
  )

  return (
    <>
      <Card>
        <AddCourierForm />
      </Card>
      {query.isError && !query.data && <QueryError onRetry={() => query.refetch()} />}
      {query.isLoading && <Skeleton height={160} />}
      {query.data?.length === 0 && <EmptyState title={t('admin.couriers.empty')} />}
      <ul className={styles.list}>
        {query.data?.map((courier) => (
          <li key={courier.id} className={styles.row}>
            <span className={styles.main}>
              <span className={styles.name}>{courier.name}</span>
              <span className={styles.muted}>
                {courier.telegram_id}
                {courier.phone && ` · ${courier.phone}`}
              </span>
            </span>
            {courier.active_deliveries > 0 && (
              <Badge>{t('admin.couriers.active', { count: courier.active_deliveries })}</Badge>
            )}
            {courier.is_active ? (
              <PillButton
                variant="secondary"
                className={styles.small}
                disabled={toggle.isPending}
                onClick={() => setToDeactivate(courier)}
              >
                {t('admin.common.deactivate')}
              </PillButton>
            ) : (
              <PillButton
                variant="secondary"
                className={styles.small}
                disabled={toggle.isPending}
                onClick={() => toggle.mutate({ id: courier.id, active: true })}
              >
                {t('admin.common.activate')}
              </PillButton>
            )}
          </li>
        ))}
      </ul>
      <ConfirmDialog
        open={toDeactivate !== null}
        title={t('admin.couriers.deactivateTitle', { name: toDeactivate?.name ?? '' })}
        message={t('admin.couriers.deactivateMessage')}
        confirmLabel={t('admin.common.deactivate')}
        busy={toggle.isPending}
        error={toggle.error ? t(adminErrorKey(toggle.error)) : null}
        onCancel={() => {
          toggle.reset()
          setToDeactivate(null)
        }}
        onConfirm={() =>
          toDeactivate &&
          toggle.mutate(
            { id: toDeactivate.id, active: false },
            { onSuccess: () => setToDeactivate(null) },
          )
        }
      />
    </>
  )
}

function DeliveriesTab() {
  const { t, i18n } = useTranslation()
  const query = useAdminShipments()
  const [toRelease, setToRelease] = useState<AdminShipment | null>(null)
  const release = useDispatchMutation((shipmentId: number) => forceRelease(shipmentId))

  if (query.isError && !query.data) return <QueryError onRetry={() => query.refetch()} />
  if (!query.data) return <Skeleton height={160} />
  if (query.data.length === 0) return <EmptyState title={t('admin.couriers.noDeliveries')} />

  return (
    <>
      <ul className={styles.list}>
        {query.data.map((shipment) => (
          <li key={shipment.id} className={styles.row}>
            <span className={styles.main}>
              <Link to={`/admin/orders/${shipment.order_id}`} className={styles.name}>
                {t('admin.orders.number', { id: shipment.order_id })}
              </Link>
              <span className={styles.muted}>
                {shipment.courier_name ?? '—'} ·{' '}
                {formatDateTime(shipment.picked_up_at ?? shipment.assigned_at, i18n.language)}
              </span>
            </span>
            <Badge tone={shipment.status === 'shipped' ? 'positive' : 'neutral'}>
              {t(`admin.couriers.shipmentStatus.${shipment.status}`)}
            </Badge>
            <PillButton
              variant="secondary"
              className={styles.small}
              disabled={release.isPending}
              onClick={() => setToRelease(shipment)}
            >
              {t('admin.couriers.release')}
            </PillButton>
          </li>
        ))}
      </ul>
      <ConfirmDialog
        open={toRelease !== null}
        title={t('admin.couriers.releaseTitle', { id: toRelease?.order_id ?? '' })}
        message={
          toRelease?.status === 'shipped'
            ? t('admin.couriers.releaseShippedMessage')
            : t('admin.couriers.releaseMessage')
        }
        confirmLabel={t('admin.couriers.release')}
        busy={release.isPending}
        error={release.error ? t(adminErrorKey(release.error)) : null}
        onCancel={() => {
          release.reset()
          setToRelease(null)
        }}
        onConfirm={() =>
          toRelease && release.mutate(toRelease.id, { onSuccess: () => setToRelease(null) })
        }
      />
    </>
  )
}

function MapTab() {
  const { t } = useTranslation()
  const query = useCourierLocations()

  if (query.isError && !query.data) return <QueryError onRetry={() => query.refetch()} />
  if (!query.data) return <Skeleton height={400} />

  return (
    <>
      {query.data.length === 0 && <p className={styles.muted}>{t('admin.couriers.nobodyOnMap')}</p>}
      <Suspense fallback={<Skeleton height={400} />}>
        <CouriersMap
          locations={query.data}
          label={t('admin.couriers.mapLabel')}
          className={styles.map}
        />
      </Suspense>
      <ul className={styles.list}>
        {query.data.map((location) => (
          <li key={location.courier_id} className={styles.row}>
            <span className={styles.main}>
              <span className={styles.name}>{location.name}</span>
              <span className={styles.muted}>
                {t('admin.couriers.active', { count: location.active_deliveries })}
              </span>
            </span>
            {location.is_stale && <Badge tone="warning">{t('admin.couriers.stale')}</Badge>}
          </li>
        ))}
      </ul>
    </>
  )
}

export function CouriersScreen() {
  const { t } = useTranslation()
  const [params, setParams] = useSearchParams()
  const tab = (TABS as string[]).includes(params.get('tab') ?? '')
    ? (params.get('tab') as Tab)
    : 'couriers'

  return (
    <div className={styles.screen}>
      <PageHeader title={t('admin.nav.couriers')} />
      <div role="tablist" className={styles.tabs}>
        {TABS.map((id) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={tab === id}
            className={[styles.tab, tab === id ? styles.activeTab : ''].join(' ')}
            onClick={() => setParams({ tab: id }, { replace: true })}
          >
            {t(`admin.couriers.tabs.${id}`)}
          </button>
        ))}
      </div>
      <EditGate permission="couriers.manage">
        {tab === 'couriers' && <CouriersTab />}
        {tab === 'deliveries' && <DeliveriesTab />}
      </EditGate>
      {tab === 'map' && <MapTab />}
    </div>
  )
}
