import { useEffect, useRef } from 'react'

import type { TelegramLoginData } from '../types'

const WIDGET_SRC = 'https://telegram.org/js/telegram-widget.js?22'
const CALLBACK = '__onAdminTelegramAuth'

declare global {
  interface Window {
    [CALLBACK]?: (user: TelegramLoginData) => void
  }
}

interface TelegramLoginButtonProps {
  botUsername: string
  onAuth: (user: TelegramLoginData) => void
}

/**
 * Telegram's own Login Widget. It renders an iframe from telegram.org and calls a global
 * function with the signed user data, which the API verifies against the bot token.
 */
export function TelegramLoginButton({ botUsername, onAuth }: TelegramLoginButtonProps) {
  const container = useRef<HTMLDivElement>(null)
  const latestOnAuth = useRef(onAuth)
  useEffect(() => {
    latestOnAuth.current = onAuth
  }, [onAuth])

  useEffect(() => {
    const host = container.current
    if (!host) return

    window[CALLBACK] = (user) => latestOnAuth.current(user)
    const script = document.createElement('script')
    script.src = WIDGET_SRC
    script.async = true
    script.setAttribute('data-telegram-login', botUsername)
    script.setAttribute('data-size', 'large')
    script.setAttribute('data-radius', '999')
    script.setAttribute('data-onauth', `${CALLBACK}(user)`)
    host.appendChild(script)

    return () => {
      delete window[CALLBACK]
      host.replaceChildren()
    }
  }, [botUsername])

  return <div ref={container} data-testid="telegram-login" />
}
