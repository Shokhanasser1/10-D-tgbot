import { CircleUserRound, Search, ShoppingBag } from 'lucide-react'
import { Outlet, useNavigate } from 'react-router-dom'

import { IconButton } from '../shared/ui/IconButton'
import styles from './AppShell.module.css'

export function AppShell() {
  const navigate = useNavigate()

  return (
    <div className={styles.shell}>
      <header className={styles.topBar}>
        <IconButton aria-label="Profile">
          <CircleUserRound size={20} />
        </IconButton>
        <div className={styles.spacer} />
        <IconButton aria-label="Search">
          <Search size={18} />
        </IconButton>
        <IconButton aria-label="Cart" onClick={() => navigate('/cart')}>
          <ShoppingBag size={18} />
        </IconButton>
      </header>
      <main className={styles.content}>
        <Outlet />
      </main>
    </div>
  )
}
