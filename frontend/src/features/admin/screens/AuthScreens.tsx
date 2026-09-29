import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { isTelegramEnv } from '../../../shared/telegram/webApp'
import { PillButton } from '../../../shared/ui/PillButton'
import { inputClass } from '../components/inputClass'
import { TelegramLoginButton } from '../components/TelegramLoginButton'
import { Field } from '../components/ui'
import { adminErrorKey, isStatus } from '../errors'
import { useLogin, useLogout, usePasswordLogin } from '../hooks'
import styles from './AuthScreens.module.css'

function botUsername(): string | undefined {
  const raw = import.meta.env.VITE_TELEGRAM_BOT_USERNAME as string | undefined
  return raw?.trim().replace(/^@/, '') || undefined
}

function signInError(t: (key: string) => string, error: unknown): string | null {
  if (!error) return null
  if (isStatus(error, 401)) return t('admin.auth.wrongCredentials')
  if (isStatus(error, 403)) return t('admin.auth.notAdmin')
  if (isStatus(error, 429)) return t('admin.auth.tooMany')
  return t(adminErrorKey(error))
}

export function LoginScreen() {
  const { t } = useTranslation()
  const telegramLogin = useLogin()
  const passwordLogin = usePasswordLogin()
  const bot = botUsername()
  const [login, setLogin] = useState('')
  const [password, setPassword] = useState('')

  function submit(event: FormEvent) {
    event.preventDefault()
    passwordLogin.mutate({ login: login.trim(), password })
  }

  const error = signInError(t, passwordLogin.error) ?? signInError(t, telegramLogin.error)
  const busy = passwordLogin.isPending || telegramLogin.isPending

  return (
    <div className={styles.screen}>
      <h1 className={styles.title}>{t('admin.auth.title')}</h1>
      <form className={styles.form} onSubmit={submit}>
        <Field label={t('admin.password.login')}>
          {(id) => (
            <input
              id={id}
              className={inputClass}
              autoComplete="username"
              value={login}
              required
              onChange={(event) => setLogin(event.target.value)}
            />
          )}
        </Field>
        <Field label={t('admin.password.password')}>
          {(id) => (
            <input
              id={id}
              type="password"
              className={inputClass}
              autoComplete="current-password"
              value={password}
              required
              onChange={(event) => setPassword(event.target.value)}
            />
          )}
        </Field>
        <PillButton type="submit" disabled={busy}>
          {t('admin.auth.signIn')}
        </PillButton>
      </form>
      {error && (
        <p role="alert" className={styles.error}>
          {error}
        </p>
      )}
      {bot && (
        <>
          <p className={styles.divider}>{t('admin.auth.orTelegram')}</p>
          <TelegramLoginButton botUsername={bot} onAuth={(user) => telegramLogin.mutate(user)} />
        </>
      )}
      <p className={styles.text}>{t('admin.auth.noPasswordYet')}</p>
    </div>
  )
}

export function NoAccessScreen() {
  const { t } = useTranslation()
  const logout = useLogout()

  return (
    <div className={styles.screen}>
      <h1 className={styles.title}>{t('admin.auth.noAccessTitle')}</h1>
      <p className={styles.text}>{t('admin.auth.noAccess')}</p>
      {!isTelegramEnv() && (
        <button type="button" className={styles.link} onClick={() => logout.mutate()}>
          {t('admin.auth.otherAccount')}
        </button>
      )}
    </div>
  )
}
