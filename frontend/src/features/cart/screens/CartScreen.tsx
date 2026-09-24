import { useTranslation } from 'react-i18next'

import { EmptyState } from '../../../shared/ui/EmptyState'
import { QueryError } from '../../../shared/ui/QueryError'
import { Skeleton } from '../../../shared/ui/Skeleton'
import { CartLineItem } from '../components/CartLineItem'
import { CartSummary } from '../components/CartSummary'
import { useCart } from '../hooks'
import styles from './CartScreen.module.css'

export function CartScreen() {
  const { t } = useTranslation()
  const cartQuery = useCart()

  if (cartQuery.isLoading) {
    return (
      <div className={styles.screen}>
        <Skeleton height={72} />
        <Skeleton height={72} />
        <Skeleton height={72} />
      </div>
    )
  }

  if (cartQuery.isError) {
    return <QueryError onRetry={() => cartQuery.refetch()} />
  }

  const items = cartQuery.data?.items ?? []

  if (items.length === 0) {
    return <EmptyState title={t('cart.empty')} description={t('cart.emptyDescription')} />
  }

  return (
    <div className={styles.screen}>
      <div className={styles.list}>
        {items.map((item) => (
          <CartLineItem key={item.id} item={item} />
        ))}
      </div>
      <CartSummary subtotal={cartQuery.data?.subtotal ?? '0'} />
    </div>
  )
}
