interface PriceProps {
  amount: number | string
  currency: string
  locale?: string
}

export function Price({ amount, currency, locale }: PriceProps) {
  const formatted = new Intl.NumberFormat(locale, {
    style: 'currency',
    currency,
  }).format(Number(amount))

  return <span>{formatted}</span>
}
