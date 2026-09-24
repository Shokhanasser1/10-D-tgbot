import { useNavigate } from 'react-router-dom'

import { Card } from '../../../shared/ui/Card'
import { Price } from '../../../shared/ui/Price'
import type { ProductListItem } from '../types'
import styles from './ProductCard.module.css'

interface ProductCardProps {
  product: ProductListItem
  currency: string
}

export function ProductCard({ product, currency }: ProductCardProps) {
  const navigate = useNavigate()

  return (
    <Card
      className={styles.card}
      role="button"
      tabIndex={0}
      onClick={() => navigate(`/products/${product.id}`)}
      onKeyDown={(event) => {
        if (event.key === 'Enter') navigate(`/products/${product.id}`)
      }}
    >
      <div className={styles.imageWrap}>
        {product.thumbnail_url ? (
          <img src={product.thumbnail_url} alt={product.name} className={styles.image} />
        ) : (
          <div className={styles.imagePlaceholder} />
        )}
      </div>
      <p className={styles.name}>{product.name}</p>
      <Price amount={product.base_price} currency={currency} />
    </Card>
  )
}
