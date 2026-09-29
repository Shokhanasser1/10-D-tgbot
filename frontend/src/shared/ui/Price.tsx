import { formatMoney } from '../money/formatMoney'

interface PriceProps {
  amount: number | string
  currency: string
  locale?: string
}

export function Price({ amount, currency, locale }: PriceProps) {
  return <span>{formatMoney(amount, currency, locale)}</span>
}
