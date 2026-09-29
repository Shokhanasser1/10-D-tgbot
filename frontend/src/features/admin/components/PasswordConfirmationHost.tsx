import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import { confirmPassword } from '../api'
import { setConfirmationHandler } from '../confirmation'
import { isStatus } from '../errors'
import type { AdminMe } from '../types'
import { ConfirmDialog } from './ui'

/**
 * Answers the API's "confirm with your password" for the whole admin panel (Spec 7): shows a
 * password dialog, confirms it, and lets the waiting action be sent again. Without a password
 * the admin is sent to the profile to set one.
 */
export function PasswordConfirmationHost({ me }: { me: AdminMe }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const settle = useRef<((confirmed: boolean) => void) | null>(null)

  useEffect(() => {
    setConfirmationHandler(() => {
      if (!me.has_password) {
        navigate('/admin/profile')
        return Promise.resolve(false)
      }
      setError(null)
      setOpen(true)
      return new Promise<boolean>((resolve) => {
        settle.current = resolve
      })
    })
    return () => setConfirmationHandler(null)
  }, [me.has_password, navigate])

  const finish = (confirmed: boolean) => {
    setOpen(false)
    settle.current?.(confirmed)
    settle.current = null
  }

  return (
    <ConfirmDialog
      open={open}
      title={t('admin.password.confirmTitle')}
      message={t('admin.password.confirmMessage')}
      inputLabel={t('admin.password.password')}
      password
      confirmLabel={t('admin.password.confirm')}
      busy={busy}
      error={error}
      onCancel={() => finish(false)}
      onConfirm={async (password) => {
        setBusy(true)
        setError(null)
        try {
          await confirmPassword(password)
          finish(true)
        } catch (failure) {
          setError(
            isStatus(failure, 429) ? t('admin.auth.tooMany') : t('admin.password.wrongPassword'),
          )
        } finally {
          setBusy(false)
        }
      }}
    />
  )
}
