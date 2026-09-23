import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'

import { getTelegramUser } from '../telegram/webApp'
import en from './locales/en.json'
import ru from './locales/ru.json'
import uz from './locales/uz.json'

const STORAGE_KEY = 'locale'
export const SUPPORTED_LOCALES = ['en', 'ru', 'uz'] as const
export type SupportedLocale = (typeof SUPPORTED_LOCALES)[number]

function isSupportedLocale(value: string | undefined): value is SupportedLocale {
  return !!value && (SUPPORTED_LOCALES as readonly string[]).includes(value)
}

function getStoredLocale(): string | undefined {
  try {
    return localStorage.getItem(STORAGE_KEY) ?? undefined
  } catch {
    return undefined
  }
}

function resolveInitialLocale(): SupportedLocale {
  const stored = getStoredLocale()
  if (isSupportedLocale(stored)) return stored

  const telegramLocale = getTelegramUser()?.language_code
  if (isSupportedLocale(telegramLocale)) return telegramLocale

  return 'en'
}

void i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    ru: { translation: ru },
    uz: { translation: uz },
  },
  lng: resolveInitialLocale(),
  fallbackLng: 'en',
  interpolation: { escapeValue: false },
})

export function setLocale(locale: SupportedLocale): void {
  void i18n.changeLanguage(locale)
  try {
    localStorage.setItem(STORAGE_KEY, locale)
  } catch {
    // localStorage unavailable (private browsing, etc.) — locale just won't persist.
  }
}

export default i18n
