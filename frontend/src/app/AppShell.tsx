import { CircleUserRound, ShoppingBag } from 'lucide-react'
import { Outlet, useNavigate } from 'react-router-dom'

import { useCart } from '../features/cart/hooks'
import { IconButton } from '../shared/ui/IconButton'
import styles from './AppShell.module.css'

export function AppShell() {
  const navigate = useNavigate()
  const cartQuery = useCart()
  const itemCount = cartQuery.data?.items.reduce((sum, item) => sum + item.qty, 0) ?? 0

  return (
    <div className={styles.shell}>
      <header className={styles.topBar}>
        <IconButton aria-label="My orders" onClick={() => navigate('/orders')}>
          <CircleUserRound size={20} />
        </IconButton>
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
