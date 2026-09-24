import { CircleUserRound, Settings, ShoppingBag, Truck } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Outlet, useNavigate } from 'react-router-dom'

import { useIsAdmin } from '../features/admin/entry'
import { useCart } from '../features/cart/hooks'
import { useCourierProfile } from '../features/courier/hooks'
import { IconButton } from '../shared/ui/IconButton'
import styles from './AppShell.module.css'

export function AppShell() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const cartQuery = useCart()
  const courierQuery = useCourierProfile()
  const adminQuery = useIsAdmin()
  const itemCount = cartQuery.data?.items.reduce((sum, item) => sum + item.qty, 0) ?? 0

  return (
    <div className={styles.shell}>
      <header className={styles.topBar}>
        <IconButton aria-label="My orders" onClick={() => navigate('/orders')}>
          <CircleUserRound size={20} />
        </IconButton>
        {/* Only couriers get this; for everyone else the profile is null (or failed to load). */}
        {courierQuery.data && (
          <IconButton aria-label={t('courier.nav')} onClick={() => navigate('/courier')}>
            <Truck size={18} />
          </IconButton>
        )}
        {/* Inside Telegram there is no address bar, so admins need a way in. */}
        {adminQuery.data && (
          <IconButton aria-label={t('admin.open')} onClick={() => navigate('/admin')}>
            <Settings size={18} />
          </IconButton>
        )}
        <div className={styles.spacer} />
        <div className={styles.cartButtonWrap}>
          <IconButton aria-label="Cart" onClick={() => navigate('/cart')}>
            <ShoppingBag size={18} />
          </IconButton>
          {itemCount > 0 && <span className={styles.badge}>{itemCount}</span>}
        </div>
      </header>
      <main className={styles.content}>
        <Outlet />
      </main>
    </div>
  )
}
