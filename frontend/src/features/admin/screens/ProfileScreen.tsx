import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { Card } from '../../../shared/ui/Card'
import { PillButton } from '../../../shared/ui/PillButton'
import { inputClass } from '../components/inputClass'
import { ErrorNote, Field, PageHeader } from '../components/ui'
import { adminErrorKey } from '../errors'
import { useChangePassword } from '../hooks'
import type { AdminMe } from '../types'
import styles from './AuthScreens.module.css'

const MIN_PASSWORD = 10

interface ProfileScreenProps {
  me: AdminMe
  /** After an owner's reset: the admin must choose a new password before anything else. */
  forced?: boolean
}

export function ProfileScreen({ me, forced = false }: ProfileScreenProps) {
  const { t } = useTranslation()
  const change = useChangePassword()
  const [login, setLogin] = useState(me.login ?? '')
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [repeat, setRepeat] = useState('')
  const [problem, setProblem] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  // A first password, or one replacing a temporary password, needs no current one.
  const needsCurrent = me.has_password && !me.must_change_password

  function submit(event: FormEvent) {
    event.preventDefault()
    setSaved(false)
    if (next.length < MIN_PASSWORD) return setProblem(t('admin.password.tooShort'))
    if (next !== repeat) return setProblem(t('admin.password.mismatch'))
    setProblem(null)
    change.mutate(
      {
        login: login.trim() || undefined,
        current_password: needsCurrent ? current : undefined,
        new_password: next,
      },
      {
        onSuccess: () => {
          setCurrent('')
          setNext('')
          setRepeat('')
          setSaved(true)
        },
      },
    )
  }

  return (
    <div className={styles.profile}>
      <PageHeader title={t('admin.password.profileTitle')} />
      {forced && (
        <p role="alert" className={styles.error}>
          {t('admin.password.mustChange')}
        </p>
      )}
      <Card className={styles.card}>
        <p className={styles.text}>
          {t('admin.password.who', { name: me.display_name, role: t(`admin.roles.${me.role}`) })}
        </p>
        <p className={styles.text}>
          {me.has_password ? t('admin.password.hasPassword') : t('admin.password.noPassword')}
        </p>
        <form className={styles.form} onSubmit={submit}>
          <Field label={t('admin.password.login')} hint={t('admin.password.loginHint')}>
            {(id) => (
              <input
                id={id}
                className={inputClass}
                autoComplete="username"
                value={login}
                maxLength={32}
                required
                onChange={(event) => setLogin(event.target.value)}
              />
            )}
          </Field>
          {needsCurrent && (
            <Field label={t('admin.password.current')}>
              {(id) => (
                <input
                  id={id}
                  type="password"
                  className={inputClass}
                  autoComplete="current-password"
                  value={current}
                  required
                  onChange={(event) => setCurrent(event.target.value)}
                />
              )}
            </Field>
          )}
          <Field label={t('admin.password.new')} hint={t('admin.password.newHint')}>
            {(id) => (
              <input
                id={id}
                type="password"
                className={inputClass}
                autoComplete="new-password"
                value={next}
                required
                onChange={(event) => setNext(event.target.value)}
              />
            )}
          </Field>
          <Field label={t('admin.password.repeat')}>
            {(id) => (
              <input
                id={id}
                type="password"
                className={inputClass}
                autoComplete="new-password"
                value={repeat}
                required
                onChange={(event) => setRepeat(event.target.value)}
              />
            )}
          </Field>
          <ErrorNote message={problem ?? (change.error ? t(adminErrorKey(change.error)) : null)} />
          {saved && (
            <p role="status" className={styles.text}>
              {t('admin.password.saved')}
            </p>
          )}
          <PillButton type="submit" disabled={change.isPending}>
            {t('admin.password.save')}
          </PillButton>
        </form>
      </Card>
    </div>
  )
}
