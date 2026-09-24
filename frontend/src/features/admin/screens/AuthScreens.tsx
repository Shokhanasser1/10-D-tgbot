import { useTranslation } from 'react-i18next'

import { isTelegramEnv } from '../../../shared/telegram/webApp'
import { TelegramLoginButton } from '../components/TelegramLoginButton'
import { adminErrorKey, isStatus } from '../errors'
import { useLogin, useLogout } from '../hooks'
import styles from './AuthScreens.module.css'

function botUsername(): string | undefined {
  const raw = import.meta.env.VITE_TELEGRAM_BOT_USERNAME as string | undefined
  return raw?.trim().replace(/^@/, '') || undefined
}

export function LoginScreen() {
  const { t } = useTranslation()
  const login = useLogin()
  const bot = botUsername()

  let error: string | null = null
  if (login.error) {
    error = isStatus(login.error, 403)
      ? t('admin.auth.notAdmin')
      : isStatus(login.error, 429)
        ? t('admin.auth.tooMany')
        : t(adminErrorKey(login.error))
  }

  return (
    <div className={styles.screen}>
      <h1 className={styles.title}>{t('admin.auth.title')}</h1>
      <p className={styles.text}>{t('admin.auth.prompt')}</p>
      {bot ? (
        <TelegramLoginButton botUsername={bot} onAuth={(user) => login.mutate(user)} />
      ) : (
        <p role="alert" className={styles.error}>
          {t('admin.auth.notConfigured')}
        </p>
      )}
      {login.isPending && <p className={styles.text}>{t('admin.auth.signingIn')}</p>}
      {error && (
        <p role="alert" className={styles.error}>
          {error}
        </p>
      )}
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
