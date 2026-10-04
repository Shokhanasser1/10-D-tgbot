import { type ReactNode, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Navigate } from 'react-router-dom'

import { useIsAdmin } from '../features/admin/entry'
import { useCourierProfile } from '../features/courier/hooks'
import { Skeleton } from '../shared/ui/Skeleton'
import {
  decideLaunch,
  finishLaunch,
  isLaunchPending,
  LAUNCH_TIMEOUT_MS,
  type LaunchDecision,
} from './launch'
import styles from './LaunchGate.module.css'

interface LaunchGateProps {
  children: ReactNode
  /** How long the role checks may take before the shop is shown anyway. */
  timeoutMs?: number
}

/**
 * Wraps the shop. On a launch at `/` it holds the shop back until it knows the user's role,
 * then sends an admin to the panel and a courier to their screen (Spec 8 §4). The checks are
 * the same queries the shell uses for its icons, so the cache shares one request each.
 */
export function LaunchGate({ children, timeoutMs = LAUNCH_TIMEOUT_MS }: LaunchGateProps) {
  const { t } = useTranslation()
  const [decision, setDecision] = useState<LaunchDecision>(() =>
    isLaunchPending() ? 'deciding' : 'shop',
  )
  const [timedOut, setTimedOut] = useState(false)
  const adminQuery = useIsAdmin()
  const courierQuery = useCourierProfile()

  const deciding = decision === 'deciding'
  // A failed check is a plain "no": the shop still works, and the icons appear if it recovers.
  const isAdmin = adminQuery.isPending ? undefined : adminQuery.data === true
  const isCourier = courierQuery.isPending ? undefined : !!courierQuery.data
  const next = deciding ? decideLaunch(isAdmin, isCourier, timedOut) : decision

  useEffect(() => {
    if (!deciding) return
    const timer = setTimeout(() => setTimedOut(true), timeoutMs)
    return () => clearTimeout(timer)
  }, [deciding, timeoutMs])

  useEffect(() => {
    if (!deciding || next === 'deciding') return
    // Before navigating: coming back to `/` later must show the shop, not decide again.
    finishLaunch()
    setDecision(next)
  }, [deciding, next])

  if (decision === 'admin') return <Navigate to="/admin" replace />
  if (decision === 'courier') return <Navigate to="/courier" replace />
  if (decision === 'shop') return <>{children}</>
  return (
    <div className={styles.skeleton} role="status" aria-label={t('common.loading')}>
      <Skeleton height={40} radius="999px" />
      <Skeleton height={160} />
      <Skeleton height={160} />
    </div>
  )
}
