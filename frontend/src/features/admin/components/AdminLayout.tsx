import {
  ClipboardList,
  LayoutDashboard,
  LogOut,
  type LucideIcon,
  Package,
  Truck,
  Users,
} from 'lucide-react'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { NavLink } from 'react-router-dom'

import { SUPPORTED_LOCALES, type SupportedLocale, setLocale } from '../../../shared/i18n'
import { isTelegramEnv } from '../../../shared/telegram/webApp'
import { useLogout } from '../hooks'
import { type AdminSection, sectionsFor } from '../permissions'
import type { AdminMe } from '../types'
import styles from './AdminLayout.module.css'

const ICONS: Record<AdminSection, LucideIcon> = {
  summary: LayoutDashboard,
  catalog: Package,
  orders: ClipboardList,
  couriers: Truck,
  admins: Users,
}

interface AdminLayoutProps {
  me: AdminMe
  children: ReactNode
}

export function AdminLayout({ me, children }: AdminLayoutProps) {
  const { t, i18n } = useTranslation()
  const logout = useLogout()

  return (
    <div className={styles.layout}>
      <aside className={styles.sidebar}>
        <div className={styles.brand}>{t('admin.title')}</div>
        <nav aria-label={t('admin.title')} className={styles.nav}>
          {sectionsFor(me.role).map((section) => {
            const Icon = ICONS[section]
            return (
              <NavLink
                key={section}
                to={`/admin/${section}`}
                className={({ isActive }) =>
                  [styles.navItem, isActive ? styles.active : ''].join(' ')
                }
              >
                <Icon size={20} aria-hidden />
                <span>{t(`admin.nav.${section}`)}</span>
              </NavLink>
            )
          })}
        </nav>
      </aside>

      <div className={styles.main}>
        <header className={styles.header}>
          <div className={styles.who}>
            <span className={styles.name}>{me.display_name}</span>
            <span className={styles.role}>{t(`admin.roles.${me.role}`)}</span>
          </div>
          <select
            aria-label={t('admin.language')}
            className={styles.language}
            value={i18n.language}
            onChange={(event) => setLocale(event.target.value as SupportedLocale)}
          >
            {SUPPORTED_LOCALES.map((locale) => (
              <option key={locale} value={locale}>
                {locale.toUpperCase()}
              </option>
            ))}
          </select>
          {!isTelegramEnv() && (
            <button
              type="button"
              className={styles.logout}
              aria-label={t('admin.auth.logout')}
              onClick={() => logout.mutate()}
            >
              <LogOut size={18} aria-hidden />
            </button>
          )}
        </header>
        <main className={styles.content}>{children}</main>
      </div>
    </div>
  )
}
