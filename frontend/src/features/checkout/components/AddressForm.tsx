import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { LazyMapPicker } from '../../../shared/map/LazyMapPicker'
import type { Coordinates, DeliveryAddress } from '../../../shared/types'
import { PillButton } from '../../../shared/ui/PillButton'
import styles from './AddressForm.module.css'

interface AddressFormProps {
  onSubmit: (address: DeliveryAddress) => void
  isSubmitting: boolean
}

const EMPTY_ADDRESS: DeliveryAddress = {
  street: '',
  city: '',
  postal_code: '',
  country: '',
  phone: '',
  notes: '',
}

export function AddressForm({ onSubmit, isSubmitting }: AddressFormProps) {
  const { t } = useTranslation()
  const [address, setAddress] = useState<DeliveryAddress>(EMPTY_ADDRESS)
  const [pin, setPin] = useState<Coordinates | null>(null)

  function update<K extends keyof DeliveryAddress>(key: K, value: DeliveryAddress[K]) {
    setAddress((prev) => ({ ...prev, [key]: value }))
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    // Without a pin the coordinate keys are left out altogether rather than sent as null.
    onSubmit(pin ? { ...address, latitude: pin.latitude, longitude: pin.longitude } : address)
  }

  return (
    <form className={styles.form} onSubmit={handleSubmit}>
      <input
        required
        placeholder={t('checkout.street')}
        value={address.street}
        onChange={(event) => update('street', event.target.value)}
        className={styles.input}
      />
      <input
        required
        placeholder={t('checkout.city')}
        value={address.city}
        onChange={(event) => update('city', event.target.value)}
        className={styles.input}
      />
      <input
        required
        placeholder={t('checkout.postalCode')}
        value={address.postal_code}
        onChange={(event) => update('postal_code', event.target.value)}
        className={styles.input}
      />
      <input
        required
        placeholder={t('checkout.country')}
        value={address.country}
        onChange={(event) => update('country', event.target.value)}
        className={styles.input}
      />
      <input
        required
        type="tel"
        placeholder={t('checkout.phone')}
        value={address.phone}
        onChange={(event) => update('phone', event.target.value)}
        className={styles.input}
      />
      <textarea
        placeholder={t('checkout.notes')}
        value={address.notes ?? ''}
        onChange={(event) => update('notes', event.target.value)}
        className={styles.textarea}
      />
      <LazyMapPicker value={pin} onChange={setPin} />
      <PillButton type="submit" disabled={isSubmitting} className={styles.submit}>
        {t('checkout.continue')}
      </PillButton>
    </form>
  )
}
