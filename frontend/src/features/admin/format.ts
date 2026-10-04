export function formatDateTime(value: string | null, locale: string): string {
  if (!value) return '—'
  return new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'short' }).format(
    new Date(value),
  )
}

export { formatMoney } from '../../shared/money/formatMoney'

/** A rate as typed by people: "10.00" -> "10", "12.50" -> "12.5" (Spec 11). */
export function formatPercent(value: string): string {
  return String(Number(value))
}
