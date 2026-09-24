import { Trash2 } from 'lucide-react'

import { DEFAULT_CURRENCY } from '../../../shared/constants'
import { Price } from '../../../shared/ui/Price'
import { QuantityStepper } from '../../../shared/ui/QuantityStepper'
import { useRemoveCartItem, useUpdateCartItem } from '../hooks'
import type { CartItem } from '../types'
import styles from './CartLineItem.module.css'

interface CartLineItemProps {
  item: CartItem
}

export function CartLineItem({ item }: CartLineItemProps) {
  const updateItem = useUpdateCartItem()
  const removeItem = useRemoveCartItem()

  return (
    <div className={styles.row}>
      <div className={styles.imageWrap}>
        {item.thumbnail_url ? (
          <img src={item.thumbnail_url} alt={item.product_name} className={styles.image} />
        ) : (
          <div className={styles.imagePlaceholder} />
        )}
      </div>

      <div className={styles.details}>
        <p className={styles.name}>{item.product_name}</p>
        <p className={styles.sku}>{item.sku}</p>
        <Price amount={item.unit_price_snapshot} currency={DEFAULT_CURRENCY} />
      </div>

      <div className={styles.controls}>
        <button
          type="button"
          className={styles.remove}
          aria-label="Remove item"
          onClick={() => removeItem.mutate(item.id)}
        >
          <Trash2 size={16} />
        </button>
        <QuantityStepper
          value={item.qty}
          onChange={(qty) => updateItem.mutate({ itemId: item.id, qty })}
        />
      </div>
    </div>
  )
}
