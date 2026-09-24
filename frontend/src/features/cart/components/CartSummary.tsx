import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import { DEFAULT_CURRENCY } from '../../../shared/constants'
import { PillButton } from '../../../shared/ui/PillButton'
import { Price } from '../../../shared/ui/Price'
import styles from './CartSummary.module.css'

interface CartSummaryProps {
  subtotal: string
}

export function CartSummary({ subtotal }: CartSummaryProps) {
  const { t } = useTranslation()
  const navigate = useNavigate()

  return (
    <div className={styles.summary}>
      <div className={styles.row}>
        <span>{t('cart.subtotal')}</span>
        <Price amount={subtotal} currency={DEFAULT_CURRENCY} />
      </div>
      <PillButton className={styles.button} onClick={() => navigate('/checkout')}>
        {t('cart.checkout')}
      </PillButton>
    </div>
  )
}
