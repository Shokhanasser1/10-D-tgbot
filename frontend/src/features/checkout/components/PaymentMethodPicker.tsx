import { useTranslation } from 'react-i18next'

import type { PaymentMethod } from '../api'
import styles from './PaymentMethodPicker.module.css'

interface PaymentMethodPickerProps {
  methods: PaymentMethod[]
  value: PaymentMethod
  onChange: (method: PaymentMethod) => void
}

/** A choice between the shop's payment methods; nothing to choose with only one. */
export function PaymentMethodPicker({ methods, value, onChange }: PaymentMethodPickerProps) {
  const { t } = useTranslation()
  if (methods.length < 2) return null

  return (
    <fieldset className={styles.group}>
      <legend className={styles.legend}>{t('checkout.method.title')}</legend>
      {methods.map((method) => (
        <label key={method} className={styles.option} data-selected={method === value}>
          <input
            type="radio"
            name="payment-method"
            value={method}
            checked={method === value}
            onChange={() => onChange(method)}
            className={styles.radio}
          />
          <span>
            <span className={styles.name}>{t(`checkout.method.${method}`)}</span>
            <span className={styles.hint}>{t(`checkout.method.${method}Hint`)}</span>
          </span>
        </label>
      ))}
    </fieldset>
  )
}
