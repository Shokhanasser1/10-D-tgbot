import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import { DEFAULT_CURRENCY } from '../../../shared/constants'
import { Card } from '../../../shared/ui/Card'
import { EmptyState } from '../../../shared/ui/EmptyState'
import { Price } from '../../../shared/ui/Price'
import { QueryError } from '../../../shared/ui/QueryError'
import { Skeleton } from '../../../shared/ui/Skeleton'
import { OrderStatusBadge } from '../components/OrderStatusBadge'
import { useOrders } from '../hooks'
import styles from './OrdersListScreen.module.css'

export function OrdersListScreen() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const ordersQuery = useOrders()

  if (ordersQuery.isLoading) {
    return (
      <div className={styles.screen}>
        <Skeleton height={72} />
        <Skeleton height={72} />
      </div>
    )
  }

  if (ordersQuery.isError) {
    return <QueryError onRetry={() => ordersQuery.refetch()} />
  }

  const orders = ordersQuery.data ?? []

  if (orders.length === 0) {
    return <EmptyState title={t('orders.empty')} description={t('orders.emptyDescription')} />
  }

  return (
    <div className={styles.screen}>
      <h1 className={styles.title}>{t('orders.title')}</h1>
      {orders.map((order) => (
        <Card
          key={order.id}
          className={styles.card}
          role="button"
          tabIndex={0}
          onClick={() => navigate(`/orders/${order.id}`)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') navigate(`/orders/${order.id}`)
          }}
        >
          <div className={styles.row}>
            <span className={styles.orderNumber}>#{order.id}</span>
            <OrderStatusBadge status={order.status} />
          </div>
          <div className={styles.row}>
            <span className={styles.date}>{new Date(order.placed_at).toLocaleDateString()}</span>
            <Price amount={order.total} currency={order.currency || DEFAULT_CURRENCY} />
          </div>
        </Card>
      ))}
    </div>
  )
}
