import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'

import { OrderStatusBadge } from '../../orders/components/OrderStatusBadge'
import { Card } from '../../../shared/ui/Card'
import { EmptyState } from '../../../shared/ui/EmptyState'
import { PillButton } from '../../../shared/ui/PillButton'
import { QueryError } from '../../../shared/ui/QueryError'
import { Skeleton } from '../../../shared/ui/Skeleton'
import { SELLER_ORDERS_PAGE_SIZE } from '../api'
import { Badge, ErrorNote, PageHeader } from '../components/ui'
import { adminErrorKey } from '../errors'
import { formatDateTime, formatMoney } from '../format'
import { useMarkReady, useSellerOrder, useSellerOrders } from '../hooks'
import type { SellerOrderListItem } from '../types'
import detail from './OrderDetailScreen.module.css'
import list from './OrdersScreen.module.css'

/**
 * A seller's own orders (Spec 10). The API gives a seller no customer data at all, so these
 * screens cannot show any: the platform delivers.
 */
function waitingForSeller(order: SellerOrderListItem): boolean {
  return order.status === 'paid' && order.shipment_status === 'processing' && !order.ready_at
}

function SellerOrderBadge({ order }: { order: SellerOrderListItem }) {
  const { t } = useTranslation()
  if (waitingForSeller(order))
    return <Badge tone="warning">{t('admin.sellerOrders.waiting')}</Badge>
  if (order.status === 'paid' && order.shipment_status === 'processing') {
    return <Badge tone="positive">{t('admin.sellerOrders.ready')}</Badge>
  }
  return <OrderStatusBadge status={order.status} />
}

export function SellerOrdersScreen() {
  const { t, i18n } = useTranslation()
  const [offset, setOffset] = useState(0)
  const query = useSellerOrders(offset)
  const page = query.data

  return (
    <div className={list.screen}>
      <PageHeader title={t('admin.nav.orders')} />
      {query.isError && !page && <QueryError onRetry={() => query.refetch()} />}
      {query.isLoading && <Skeleton height={200} />}
      {page && page.items.length === 0 && <EmptyState title={t('admin.sellerOrders.empty')} />}

      {page && page.items.length > 0 && (
        <ul className={list.list}>
          {page.items.map((order) => (
            <li key={order.id}>
              <Link to={`/admin/orders/${order.id}`} className={list.row}>
                <span className={list.main}>
                  <span className={list.title}>{t('admin.orders.number', { id: order.id })}</span>
                  <span className={list.muted}>
                    {formatDateTime(order.placed_at, i18n.language)} ·{' '}
                    {t('admin.sellerOrders.items', { count: order.item_count })}
                  </span>
                </span>
                <span className={list.side}>
                  <span className={list.total}>
                    {formatMoney(order.subtotal, order.currency, i18n.language)}
                  </span>
                  <SellerOrderBadge order={order} />
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}

      {page && page.total > SELLER_ORDERS_PAGE_SIZE && (
        <div className={list.pager}>
          <PillButton
            variant="secondary"
            disabled={offset === 0}
            onClick={() => setOffset(Math.max(0, offset - SELLER_ORDERS_PAGE_SIZE))}
          >
            {t('admin.common.previous')}
          </PillButton>
          <PillButton
            variant="secondary"
            disabled={offset + SELLER_ORDERS_PAGE_SIZE >= page.total}
            onClick={() => setOffset(offset + SELLER_ORDERS_PAGE_SIZE)}
          >
            {t('admin.common.next')}
          </PillButton>
        </div>
      )}
    </div>
  )
}

export function SellerOrderScreen() {
  const { t, i18n } = useTranslation()
  const orderId = Number(useParams<{ orderId: string }>().orderId)
  const query = useSellerOrder(orderId)
  const ready = useMarkReady(orderId)

  const order = query.data
  if (query.isError && !order) return <QueryError onRetry={() => query.refetch()} />
  if (!order) return <Skeleton height={320} />

  const money = (amount: string) => formatMoney(amount, order.currency, i18n.language)
  const waiting = waitingForSeller(order)

  return (
    <div className={detail.screen}>
      <Link to="/admin/orders" className={detail.back}>
        ← {t('admin.orders.back')}
      </Link>
      <PageHeader
        title={t('admin.orders.number', { id: order.id })}
        actions={<SellerOrderBadge order={order} />}
      />

      <Card className={detail.card}>
        <h2 className={detail.cardTitle}>{t('admin.orders.items')}</h2>
        <ul className={detail.items}>
          {order.items.map((item) => (
            <li key={item.sku} className={detail.item}>
              <span className={detail.itemMain}>
                <span>{item.product_name}</span>
                <span className={detail.muted}>
                  {item.sku} · {item.qty} × {money(item.unit_price)}
                </span>
              </span>
            </li>
          ))}
        </ul>
        <p className={detail.muted}>
          {t('admin.orders.paymentMethod', {
            method: t(`admin.orders.method.${order.payment_method}`),
          })}
        </p>
        <dl className={detail.totals}>
          <dt className={detail.strong}>{t('admin.sellerOrders.goodsTotal')}</dt>
          <dd className={detail.strong}>{money(order.subtotal)}</dd>
        </dl>
      </Card>

      {waiting ? (
        <>
          <p className={detail.notes}>{t('admin.sellerOrders.readyHint')}</p>
          <div className={detail.actions}>
            <PillButton disabled={ready.isPending} onClick={() => ready.mutate()}>
              {t('admin.sellerOrders.markReady')}
            </PillButton>
          </div>
        </>
      ) : (
        order.ready_at &&
        order.shipment_status === 'processing' && (
          <p className={detail.muted} role="status">
            {t('admin.sellerOrders.readyDone')}
          </p>
        )
      )}
      <ErrorNote message={ready.error ? t(adminErrorKey(ready.error)) : null} />
    </div>
  )
}
