import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'

import { OrderStatusBadge } from '../../orders/components/OrderStatusBadge'
import { LazyTrackingMap } from '../../../shared/map/LazyTrackingMap'
import { Card } from '../../../shared/ui/Card'
import { PillButton } from '../../../shared/ui/PillButton'
import { QueryError } from '../../../shared/ui/QueryError'
import { Skeleton } from '../../../shared/ui/Skeleton'
import { cancelOrder, confirmManualRefund, retryRefund } from '../api'
import { Badge, ConfirmDialog, ErrorNote, PageHeader } from '../components/ui'
import { adminErrorKey } from '../errors'
import { useCan } from '../meContext'
import { formatDateTime, formatMoney } from '../format'
import { useAdminOrder, useOrderAction } from '../hooks'
import type { AdminOrder, RefundStatus } from '../types'
import styles from './OrderDetailScreen.module.css'

const SYSTEM_REASONS = new Set(['payment_expired', 'payment_setup_failed'])

const REFUND_TONE: Record<RefundStatus, 'neutral' | 'positive' | 'negative'> = {
  pending: 'neutral',
  succeeded: 'positive',
  failed: 'negative',
  manual_required: 'negative',
}

function History({ order }: { order: AdminOrder }) {
  const { t, i18n } = useTranslation()
  const steps: [string, string | null | undefined][] = [
    ['placed', order.placed_at],
    ['assigned', order.shipment?.assigned_at],
    ['pickedUp', order.shipment?.picked_up_at],
    ['delivered', order.shipment?.delivered_at],
    ['cancelled', order.cancelled_at],
  ]
  return (
    <ol className={styles.history}>
      {steps
        .filter(([, at]) => at)
        .map(([step, at]) => (
          <li key={step}>
            <span>{t(`admin.orders.history.${step}`)}</span>
            <span className={styles.muted}>{formatDateTime(at ?? null, i18n.language)}</span>
          </li>
        ))}
    </ol>
  )
}

export function OrderDetailScreen() {
  const { t, i18n } = useTranslation()
  const orderId = Number(useParams<{ orderId: string }>().orderId)
  const query = useAdminOrder(orderId)
  const [confirming, setConfirming] = useState(false)
  const cancel = useOrderAction((reason: string) => cancelOrder(orderId, reason))
  const refund = useOrderAction(() => retryRefund(orderId))
  const confirmRefund = useOrderAction(() => confirmManualRefund(orderId))
  const canCancelPaid = useCan('orders.cancel_paid')
  const canCancelUnpaid = useCan('orders.cancel_unpaid')
  const canRefund = useCan('refunds.manage')

  const order = query.data
  if (query.isError && !order) return <QueryError onRetry={() => query.refetch()} />
  if (!order) return <Skeleton height={320} />

  const address = order.delivery_address
  const pin =
    address.latitude != null && address.longitude != null
      ? { latitude: address.latitude, longitude: address.longitude }
      : null
  const money = (amount: string) => formatMoney(amount, order.currency, i18n.language)
  const customerName =
    [order.customer.first_name, order.customer.last_name].filter(Boolean).join(' ') || '—'
  const refundStatus = order.payment?.refund_status ?? null
  // Cancelling gives money back only if it was taken (cash is collected on delivery).
  const moneyTaken = order.payment?.status === 'succeeded' && order.payment.method !== 'cash'
  const mayCancel = moneyTaken ? canCancelPaid : canCancelUnpaid

  return (
    <div className={styles.screen}>
      <Link to="/admin/orders" className={styles.back}>
        ← {t('admin.orders.back')}
      </Link>
      <PageHeader
        title={t('admin.orders.number', { id: order.id })}
        actions={<OrderStatusBadge status={order.status} />}
      />

      {(order.stock_shortfall || refundStatus) && (
        <div className={styles.flags}>
          {order.stock_shortfall && <Badge tone="warning">{t('admin.orders.shortfall')}</Badge>}
          {refundStatus && (
            <Badge tone={REFUND_TONE[refundStatus]}>
              {t(`admin.orders.refund.${refundStatus}`)}
            </Badge>
          )}
        </div>
      )}

      <div className={styles.columns}>
        <Card className={styles.card}>
          <h2 className={styles.cardTitle}>{t('admin.orders.items')}</h2>
          <ul className={styles.items}>
            {order.items.map((item) => (
              <li key={item.id} className={styles.item}>
                <span className={styles.itemMain}>
                  <Link to={`/admin/catalog/products/${item.product_id}`}>
                    {item.product_name_snapshot}
                  </Link>
                  <span className={styles.muted}>
                    {item.sku} · {item.qty} × {money(item.unit_price_snapshot)}
                  </span>
                </span>
              </li>
            ))}
          </ul>
          {order.payment?.method && (
            <p className={styles.muted}>
              {t('admin.orders.paymentMethod', {
                method: t(`admin.orders.method.${order.payment.method}`),
              })}
              {order.payment.method === 'cash' &&
                order.status !== 'cancelled' &&
                ` · ${t(
                  order.payment.status === 'succeeded'
                    ? 'admin.orders.cashCollected'
                    : 'admin.orders.cashPending',
                )}`}
            </p>
          )}
          <dl className={styles.totals}>
            <dt>{t('admin.orders.subtotal')}</dt>
            <dd>{money(order.subtotal)}</dd>
            <dt>{t('admin.orders.shipping')}</dt>
            <dd>{money(order.shipping_cost)}</dd>
            <dt className={styles.strong}>{t('admin.orders.total')}</dt>
            <dd className={styles.strong}>{money(order.total)}</dd>
          </dl>
        </Card>

        <Card className={styles.card}>
          <h2 className={styles.cardTitle}>{t('admin.orders.customer')}</h2>
          <p className={styles.line}>
            {customerName}
            {order.customer.username && (
              <span className={styles.muted}> @{order.customer.username}</span>
            )}
          </p>
          <p className={styles.line}>
            <a href={`tel:${address.phone}`}>{address.phone}</a>
          </p>
          <p className={styles.line}>
            {address.street}, {address.postal_code} {address.city}, {address.country}
          </p>
          {address.notes && <p className={styles.notes}>{address.notes}</p>}
          {pin && (
            <LazyTrackingMap
              courier={null}
              destination={pin}
              label={t('admin.orders.pin')}
              className={styles.map}
            />
          )}
        </Card>

        <Card className={styles.card}>
          <h2 className={styles.cardTitle}>{t('admin.orders.delivery')}</h2>
          <p className={styles.line}>
            {order.shipment?.courier_name
              ? t('admin.orders.courier', { name: order.shipment.courier_name })
              : t('admin.orders.noCourier')}
          </p>
          <History order={order} />
          {order.cancel_reason && (
            <p className={styles.notes}>
              {t('admin.orders.cancelReason', {
                // Reasons the system sets are codes; an admin's own reason is shown as typed.
                reason: SYSTEM_REASONS.has(order.cancel_reason)
                  ? t(`admin.orders.systemReason.${order.cancel_reason}`)
                  : order.cancel_reason,
              })}
            </p>
          )}
        </Card>
      </div>

      {refundStatus === 'manual_required' && (
        <p className={styles.notes} role="status">
          {t('admin.orders.manualRefund', {
            total: money(order.payment?.amount ?? order.total),
            charge: order.payment?.provider_payment_charge_id ?? '—',
            telegram: order.payment?.telegram_payment_charge_id ?? '—',
          })}
        </p>
      )}
      <div className={styles.actions}>
        {refundStatus === 'manual_required' && canRefund && (
          <PillButton
            disabled={confirmRefund.isPending}
            onClick={() => confirmRefund.mutate(undefined)}
          >
            {t('admin.orders.confirmRefund')}
          </PillButton>
        )}
        {refundStatus === 'failed' && canRefund && (
          <PillButton disabled={refund.isPending} onClick={() => refund.mutate(undefined)}>
            {t('admin.orders.retryRefund')}
          </PillButton>
        )}
        {(order.status === 'paid' || order.status === 'processing') && mayCancel && (
          <PillButton
            variant="secondary"
            className={styles.danger}
            disabled={!order.can_cancel}
            onClick={() => setConfirming(true)}
          >
            {moneyTaken ? t('admin.orders.cancel') : t('admin.orders.cancelOnly')}
          </PillButton>
        )}
      </div>
      {order.status === 'shipped' && (
        <p className={styles.muted}>{t('admin.orders.cannotCancel')}</p>
      )}
      <ErrorNote message={refund.error ? t(adminErrorKey(refund.error)) : null} />
      <ErrorNote message={confirmRefund.error ? t(adminErrorKey(confirmRefund.error)) : null} />

      <ConfirmDialog
        open={confirming}
        title={t('admin.orders.cancelTitle', { id: order.id })}
        message={
          moneyTaken
            ? t('admin.orders.cancelMessage', { total: money(order.total) })
            : t('admin.orders.cancelMessageUnpaid')
        }
        inputLabel={t('admin.orders.reason')}
        confirmLabel={t('admin.orders.cancelConfirm')}
        busy={cancel.isPending}
        error={cancel.error ? t(adminErrorKey(cancel.error)) : null}
        onCancel={() => {
          cancel.reset()
          setConfirming(false)
        }}
        onConfirm={(reason) => cancel.mutate(reason, { onSuccess: () => setConfirming(false) })}
      />
    </div>
  )
}
