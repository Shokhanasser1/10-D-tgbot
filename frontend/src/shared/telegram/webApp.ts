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
  // Newer than the Bot API version some clients report, so treated as optional throughout.
  openLink?: (url: string) => void
  openTelegramLink?: (url: string) => void
  isVersionAtLeast?: (version: string) => boolean
  disableVerticalSwipes?: () => void
  enableVerticalSwipes?: () => void
}

declare global {
  interface Window {
    Telegram?: { WebApp: TelegramWebApp }
  }
}

// Gated on DEV so a production build never contains (or honours) a mock identity, even if
// VITE_DEV_MOCK_INIT_DATA is present in the build environment.
const DEV_MOCK_INIT_DATA = import.meta.env.DEV
  ? (import.meta.env.VITE_DEV_MOCK_INIT_DATA as string | undefined)
  : undefined

export function getWebApp(): TelegramWebApp | undefined {
  return window.Telegram?.WebApp
}

/**
 * False in a plain browser (local dev/preview) — screens fall back to an in-page action
 * button. Telegram's own script defines `window.Telegram.WebApp` even when loaded standalone
 * outside a real Telegram client, but leaves `initData` empty in that case, so checking for
 * non-empty initData (real launch params) is the reliable signal rather than object presence.
 */
export function isTelegramEnv(): boolean {
  return !!window.Telegram?.WebApp.initData
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

const WEB_URL = /^https?:\/\//i

/** Opens a web page outside the Mini App, so following a link never navigates the app away. */
export function openExternalLink(url: string): void {
  if (!WEB_URL.test(url)) return
  const webApp = getWebApp()
  if (webApp?.openLink) webApp.openLink(url)
  else window.open(url, '_blank', 'noopener')
}

/** Opens a t.me link inside Telegram (e.g. a chat with the bot). */
export function openTelegramLink(url: string): void {
  if (!WEB_URL.test(url)) return
  const webApp = getWebApp()
  if (webApp?.openTelegramLink) webApp.openTelegramLink(url)
  else window.open(url, '_blank', 'noopener')
}
