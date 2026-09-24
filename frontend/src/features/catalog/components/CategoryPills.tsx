import type { Category } from '../types'
import styles from './CategoryPills.module.css'

interface CategoryPillsProps {
  categories: Category[]
  selectedId: number | null
  onSelect: (id: number | null) => void
  allLabel: string
}

export function CategoryPills({ categories, selectedId, onSelect, allLabel }: CategoryPillsProps) {
  return (
    <div className={styles.row}>
      <button
        type="button"
        className={[styles.pill, selectedId === null ? styles.active : ''].join(' ')}
        onClick={() => onSelect(null)}
      >
        {allLabel}
      </button>
      {categories.map((category) => (
        <button
          key={category.id}
          type="button"
          className={[styles.pill, selectedId === category.id ? styles.active : ''].join(' ')}
          onClick={() => onSelect(category.id)}
        >
          {category.name}
        </button>
      ))}
    </div>
  )
}
