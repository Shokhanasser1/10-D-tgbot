import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { useCan } from '../meContext'
import type { Permission } from '../types'
import styles from './ui.module.css'

/**
 * Renders its children read-only unless the admin may edit: a disabled fieldset switches off
 * every input and button inside at once, so no control can be forgotten.
 */
export function EditGate({
  permission,
  children,
}: {
  permission: Permission
  children: ReactNode
}) {
  const { t } = useTranslation()
  const allowed = useCan(permission)
  return (
    <fieldset disabled={!allowed} className={styles.gate}>
      {!allowed && <p className={styles.readOnly}>{t('admin.common.readOnly')}</p>}
      {children}
    </fieldset>
  )
}
