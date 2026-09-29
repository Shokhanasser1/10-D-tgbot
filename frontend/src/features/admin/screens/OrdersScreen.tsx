import { useDeferredValue } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router-dom'

import { OrderStatusBadge } from '../../orders/components/OrderStatusBadge'
import type { OrderStatus } from '../../orders/types'
import { EmptyState } from '../../../shared/ui/EmptyState'
import { PillButton } from '../../../shared/ui/PillButton'
import { QueryError } from '../../../shared/ui/QueryError'
import { Skeleton } from '../../../shared/ui/Skeleton'
import { ORDERS_PAGE_SIZE } from '../api'
import { Badge, PageHeader } from '../components/ui'
import { formatDateTime, formatMoney } from '../format'
import { useAdminOrders } from '../hooks'
import { inputClass } from '../components/inputClass'
import styles from './OrdersScreen.module.css'

const STATUSES: OrderStatus[] = [
  'pending_payment',
  'paid',
  'processing',
  'shipped',
  'delivered',
  'cancelled',
]

/** Filters live in the URL, so the summary can link to "all paid orders" and back works. */
export function OrdersScreen() {
  const { t, i18n } = useTranslation()
  const [params, setParams] = useSearchParams()
  const status = params.get('status') as OrderStatus | null
  const q = params.get('q') ?? ''
  const from = params.get('from') ?? ''
  const to = params.get('to') ?? ''
  const shortfall = params.get('shortfall') === 'true'
  const offset = Number(params.get('offset')) || 0
  const deferredQ = useDeferredValue(q)

  const query = useAdminOrders({
    status: status && STATUSES.includes(status) ? [status] : undefined,
    q: deferredQ.trim() || undefined,
    from: from || undefined,
    to: to || undefined,
    shortfall: shortfall || undefined,
    offset,
  })
  const page = query.data

  function update(changes: Record<string, string | null>) {
    const next = new URLSearchParams(params)
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value)
      else next.delete(key)
    }
    if (!('offset' in changes)) next.delete('offset')
    setParams(next, { replace: true })
  }

  return (
    <div className={styles.screen}>
      <PageHeader title={t('admin.nav.orders')} />
      <div className={styles.filters}>
        <input
          type="search"
          inputMode="numeric"
          className={inputClass}
          placeholder={t('admin.orders.search')}
          aria-label={t('admin.orders.search')}
          value={q}
          onChange={(event) => update({ q: event.target.value })}
        />
        <select
          className={inputClass}
          aria-label={t('admin.orders.status')}
          value={status ?? ''}
          onChange={(event) => update({ status: event.target.value })}
        >
          <option value="">{t('admin.orders.allStatuses')}</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {t(`orders.status.${s}`)}
            </option>
          ))}
        </select>
        <input
          type="date"
          className={inputClass}
          aria-label={t('admin.orders.from')}
          value={from}
          onChange={(event) => update({ from: event.target.value })}
        />
        <input
          type="date"
          className={inputClass}
          aria-label={t('admin.orders.to')}
          value={to}
          onChange={(event) => update({ to: event.target.value })}
        />
        <label className={styles.check}>
          <input
            type="checkbox"
            checked={shortfall}
            onChange={(event) => update({ shortfall: event.target.checked ? 'true' : null })}
          />
          {t('admin.orders.onlyShortfall')}
        </label>
      </div>

      {query.isError && !page && <QueryError onRetry={() => query.refetch()} />}
      {query.isLoading && <Skeleton height={200} />}
      {page && page.items.length === 0 && <EmptyState title={t('admin.orders.empty')} />}

      {page && page.items.length > 0 && (
        <ul className={styles.list}>
          {page.items.map((order) => (
            <li key={order.id}>
              <Link to={`/admin/orders/${order.id}`} className={styles.row}>
                <span className={styles.main}>
                  <span className={styles.title}>
                    {t('admin.orders.number', { id: order.id })}
                    <span className={styles.muted}>{order.customer_name ?? order.telegram_id}</span>
                  </span>
                  <span className={styles.muted}>
                    {formatDateTime(order.placed_at, i18n.language)}
                  </span>
                  <span className={styles.badges}>
                    {order.stock_shortfall && (
                      <Badge tone="warning">{t('admin.orders.shortfall')}</Badge>
                    )}
                    {order.refund_status === 'failed' && (
                      <Badge tone="negative">{t('admin.orders.refundFailed')}</Badge>
                    )}
                    {order.refund_status === 'manual_required' && (
                      <Badge tone="negative">{t('admin.orders.refund.manual_required')}</Badge>
                    )}
                    {order.payment_method && order.payment_method !== 'stripe' && (
                      <Badge tone="neutral">
                        {t(`admin.orders.method.${order.payment_method}`)}
                      </Badge>
                    )}
                  </span>
                </span>
                <span className={styles.side}>
                  <span className={styles.total}>
                    {formatMoney(order.total, order.currency, i18n.language)}
                  </span>
                  <OrderStatusBadge status={order.status} />
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}

      {page && page.total > ORDERS_PAGE_SIZE && (
        <div className={styles.pager}>
          <PillButton
            variant="secondary"
            disabled={offset === 0}
            onClick={() => update({ offset: String(Math.max(0, offset - ORDERS_PAGE_SIZE)) })}
          >
            {t('admin.common.previous')}
          </PillButton>
          <span className={styles.muted}>
            {t('admin.common.range', {
              from: offset + 1,
              to: Math.min(offset + ORDERS_PAGE_SIZE, page.total),
              total: page.total,
            })}
          </span>
          <PillButton
            variant="secondary"
            disabled={offset + ORDERS_PAGE_SIZE >= page.total}
            onClick={() => update({ offset: String(offset + ORDERS_PAGE_SIZE) })}
          >
            {t('admin.common.next')}
          </PillButton>
        </div>
      )}
    </div>
  )
}
