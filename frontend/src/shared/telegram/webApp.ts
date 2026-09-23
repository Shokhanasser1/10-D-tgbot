export interface TelegramUser {
  id: number
  username?: string
  first_name?: string
  last_name?: string
  language_code?: string
}

interface TelegramWebAppMainButton {
  show: () => void
  hide: () => void
  enable: () => void
  disable: () => void
  onClick: (cb: () => void) => void
  offClick: (cb: () => void) => void
  setText: (text: string) => void
}

interface TelegramWebAppBackButton {
  show: () => void
  hide: () => void
  onClick: (cb: () => void) => void
  offClick: (cb: () => void) => void
}

interface TelegramWebAppHaptic {
  impactOccurred: (style: 'light' | 'medium' | 'heavy' | 'rigid' | 'soft') => void
  notificationOccurred: (type: 'error' | 'success' | 'warning') => void
}

interface TelegramWebApp {
  initData: string
  initDataUnsafe: { user?: TelegramUser }
  themeParams: Record<string, string>
  colorScheme: 'light' | 'dark'
  ready: () => void
  expand: () => void
  MainButton: TelegramWebAppMainButton
  BackButton: TelegramWebAppBackButton
  HapticFeedback: TelegramWebAppHaptic
}

declare global {
  interface Window {
    Telegram?: { WebApp: TelegramWebApp }
  }
}

const DEV_MOCK_INIT_DATA = import.meta.env.VITE_DEV_MOCK_INIT_DATA as string | undefined

export function getWebApp(): TelegramWebApp | undefined {
  return window.Telegram?.WebApp
}

export function initWebApp(): void {
  const webApp = getWebApp()
  webApp?.ready()
  webApp?.expand()
}

export function getInitDataRaw(): string {
  const webApp = getWebApp()
  if (webApp?.initData) return webApp.initData
  return DEV_MOCK_INIT_DATA ?? ''
}

export function getTelegramUser(): TelegramUser | undefined {
  return getWebApp()?.initDataUnsafe.user
}
