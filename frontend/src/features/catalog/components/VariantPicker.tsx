import type { Variant } from '../types'
import styles from './VariantPicker.module.css'

interface VariantPickerProps {
  variants: Variant[]
  selectedVariantId: number | null
  onSelect: (variantId: number) => void
}

export function VariantPicker({ variants, selectedVariantId, onSelect }: VariantPickerProps) {
  const attributeKeys = Array.from(
    new Set(variants.flatMap((variant) => Object.keys(variant.attribute_values))),
  )
  const selectedVariant = variants.find((variant) => variant.id === selectedVariantId)

  if (attributeKeys.length === 0) return null

  return (
    <div className={styles.picker}>
      {attributeKeys.map((key) => {
        const seen = new Set<string>()
        const options = variants
          .map((variant) => variant.attribute_values[key])
          .filter((value): value is string => {
            if (!value || seen.has(value)) return false
            seen.add(value)
            return true
          })

        return (
          <div key={key} className={styles.group}>
            <span className={styles.label}>{key}</span>
            <div className={styles.options}>
              {options.map((value) => {
                const match = variants.find((variant) => variant.attribute_values[key] === value)
                const isSelected = selectedVariant?.attribute_values[key] === value
                const outOfStock = match ? match.stock_qty <= 0 : false

                return (
                  <button
                    key={value}
                    type="button"
                    disabled={outOfStock}
                    className={[
                      styles.option,
                      isSelected ? styles.selected : '',
                      outOfStock ? styles.disabled : '',
                    ].join(' ')}
                    onClick={() => match && onSelect(match.id)}
                  >
                    {value}
                  </button>
                )
              })}
            </div>
          </div>
        )
      })}
    </div>
  )
}
