import type { TFunction } from 'i18next'

/**
 * Whole seconds between an ISO timestamp and `now`, never negative. The server's clock and the
 * phone's can disagree, and "-3 s ago" reads as a bug.
 */
export function secondsSince(isoTimestamp: string, now: number): number {
  const then = Date.parse(isoTimestamp)
  if (Number.isNaN(then)) return 0
  return Math.max(0, Math.floor((now - then) / 1000))
}

/** "12 s ago", "3 min ago", "2 h ago": abbreviated units, so no per-language plural forms. */
export function formatAgo(t: TFunction, seconds: number): string {
  if (seconds < 60) return t('time.secondsAgo', { n: seconds })
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return t('time.minutesAgo', { n: minutes })
  return t('time.hoursAgo', { n: Math.floor(minutes / 60) })
}
