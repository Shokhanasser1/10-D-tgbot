import { useTranslation } from 'react-i18next'

import { EmptyState } from '../../../shared/ui/EmptyState'
import { QueryError } from '../../../shared/ui/QueryError'
import { Skeleton } from '../../../shared/ui/Skeleton'
import type { ProductListItem } from '../types'
import { ProductCard } from './ProductCard'
import styles from './ProductGrid.module.css'

interface ProductGridProps {
  products: ProductListItem[]
  currency: string
  isLoading: boolean
  isError: boolean
  onRetry: () => void
}

export function ProductGrid({ products, currency, isLoading, isError, onRetry }: ProductGridProps) {
  const { t } = useTranslation()

  if (isLoading) {
    return (
      <div className={styles.grid}>
        {Array.from({ length: 6 }).map((_, index) => (
          // Static placeholder count, never reordered — index as key is safe here.
          // eslint-disable-next-line react/no-array-index-key
          <Skeleton key={index} height={180} radius="18px" />
        ))}
      </div>
    )
  }

  if (isError) {
    return <QueryError onRetry={onRetry} />
  }

  if (products.length === 0) {
    return <EmptyState title={t('catalog.empty')} />
  }

  return (
    <div className={styles.grid}>
      {products.map((product) => (
        <ProductCard key={product.id} product={product} currency={currency} />
      ))}
    </div>
  )
}
