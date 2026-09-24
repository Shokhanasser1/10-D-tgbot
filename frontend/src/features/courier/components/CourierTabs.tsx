import { useTranslation } from 'react-i18next'

import type { CourierTab } from '../types'
import styles from './CourierTabs.module.css'

interface CourierTabsProps {
  tab: CourierTab
  onChange: (tab: CourierTab) => void
  poolCount: number | null
  mineCount: number | null
}

export function CourierTabs({ tab, onChange, poolCount, mineCount }: CourierTabsProps) {
  const { t } = useTranslation()

  const tabs: { id: CourierTab; label: string; count: number | null }[] = [
    { id: 'pool', label: t('courier.tabs.pool'), count: poolCount },
    { id: 'mine', label: t('courier.tabs.mine'), count: mineCount },
  ]

  return (
    <div role="tablist" className={styles.tabs}>
      {tabs.map(({ id, label, count }) => (
        <button
          key={id}
          type="button"
          role="tab"
          aria-selected={tab === id}
          className={[styles.tab, tab === id ? styles.active : ''].join(' ')}
          onClick={() => onChange(id)}
        >
          {label}
          {count !== null && count > 0 && <span className={styles.count}>{count}</span>}
        </button>
      ))}
    </div>
  )
}
