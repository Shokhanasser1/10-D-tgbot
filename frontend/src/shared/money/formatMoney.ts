// Currencies priced in whole units in practice: showing ",00" on every price would be noise.
const WHOLE_UNIT_CURRENCIES = new Set(['UZS'])

/** "UZS 250,000" / "250 000 сум" / "€19.99", in the viewer's language. */
export function formatMoney(amount: number | string, currency: string, locale?: string): string {
  const whole = WHOLE_UNIT_CURRENCIES.has(currency.toUpperCase())
  return new Intl.NumberFormat(locale, {
    style: 'currency',
    currency,
    ...(whole ? { minimumFractionDigits: 0, maximumFractionDigits: 0 } : {}),
  }).format(Number(amount))
}
