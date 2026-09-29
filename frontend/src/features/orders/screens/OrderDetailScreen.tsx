import { useTranslation } from 'react-i18next'
import { useParams } from 'react-router-dom'

import { DEFAULT_CURRENCY } from '../../../shared/constants'
import { Card } from '../../../shared/ui/Card'
import { Price } from '../../../shared/ui/Price'
import { QueryError } from '../../../shared/ui/QueryError'
import { Skeleton } from '../../../shared/ui/Skeleton'
import { OrderStatusBadge } from '../components/OrderStatusBadge'
import { PaymentNotice } from '../components/PaymentNotice'
import { TrackingCard } from '../components/TrackingCard'
import { useOrder } from '../hooks'
import styles from './OrderDetailScreen.module.css'

export function OrderDetailScreen() {
  const { t } = useTranslation()
  const { orderId } = useParams<{ orderId: string }>()
  const orderQuery = useOrder(Number(orderId))

  if (orderQuery.isError) {
    return <QueryError onRetry={() => orderQuery.refetch()} />
  }

  if (orderQuery.isLoading || !orderQuery.data) {
    return (
      <div className={styles.screen}>
        <Skeleton height={100} />
        <Skeleton height={160} />
      </div>
    )
  }

  const order = orderQuery.data

  return (
    <div className={styles.screen}>
      <div className={styles.header}>
        <h1 className={styles.title}>#{order.id}</h1>
        <OrderStatusBadge status={order.status} />
      </div>

      <PaymentNotice order={order} />

      <TrackingCard orderId={order.id} orderStatus={order.status} />

      <Card className={styles.section}>
        <h2 className={styles.sectionTitle}>{t('orders.itemsTitle')}</h2>
        {order.items.map((item) => (
          <div key={item.id} className={styles.itemRow}>
            <span className={styles.itemName}>
              {item.product_name_snapshot} × {item.qty}
            </span>
            <Price
              amount={(Number(item.unit_price_snapshot) * item.qty).toFixed(2)}
              currency={order.currency || DEFAULT_CURRENCY}
            />
          </div>
        ))}
        <div className={styles.totalRow}>
          <span>{t('cart.subtotal')}</span>
          <Price amount={order.total} currency={order.currency || DEFAULT_CURRENCY} />
        </div>
      </Card>

      <Card className={styles.section}>
        <h2 className={styles.sectionTitle}>{t('orders.deliveryAddress')}</h2>
        <p className={styles.address}>
          {order.delivery_address.street}, {order.delivery_address.city}{' '}
          {order.delivery_address.postal_code}, {order.delivery_address.country}
        </p>
        <p className={styles.address}>{order.delivery_address.phone}</p>
        {order.delivery_address.notes && (
          <p className={styles.address}>{order.delivery_address.notes}</p>
        )}
      </Card>
    </div>
  )
}
