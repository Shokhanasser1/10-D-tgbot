import { Settings, Store } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Outlet, useNavigate } from 'react-router-dom'

import { useIsAdmin } from '../features/admin/entry'
import { IconButton } from '../shared/ui/IconButton'
import styles from './AppShell.module.css'

/**
 * The courier's own top bar (Spec 8 §5): a courier works here, so it offers the way back to
 * the shop instead of the shop's cart and orders.
 */
export function CourierShell() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const adminQuery = useIsAdmin()

  return (
    <div className={styles.shell}>
      <header className={styles.topBar}>
        <IconButton aria-label={t('nav.shop')} onClick={() => navigate('/')}>
          <Store size={18} />
        </IconButton>
        {/* Someone can be a courier and an admin; the panel is then one tap away. */}
        {adminQuery.data && (
          <IconButton aria-label={t('admin.open')} onClick={() => navigate('/admin')}>
            <Settings size={18} />
          </IconButton>
        )}
        <div className={styles.spacer} />
      </header>
      <main className={styles.content}>
        <Outlet />
      </main>
    </div>
  )
}
