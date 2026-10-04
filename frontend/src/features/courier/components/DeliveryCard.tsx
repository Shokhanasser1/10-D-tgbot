import { useTranslation } from 'react-i18next'

import { formatMoney } from '../../../shared/money/formatMoney'

import { openExternalLink } from '../../../shared/telegram/webApp'
import { Card } from '../../../shared/ui/Card'
import { PillButton } from '../../../shared/ui/PillButton'
import type { CourierDelivery } from '../types'
import styles from './DeliveryCard.module.css'
import { mapsUrl, telHref } from './mapsUrl'
import { pickupPlace } from './pickup'

interface DeliveryCardProps {
  delivery: CourierDelivery
  isBusy: boolean
  onPickup: (shipmentId: number) => void
  onDeliver: (shipmentId: number) => void
  onRelease: (shipmentId: number) => void
}

export function DeliveryCard({
  delivery,
  isBusy,
  onPickup,
  onDeliver,
  onRelease,
}: DeliveryCardProps) {
  const { t, i18n } = useTranslation()
  const { address } = delivery
  const tel = telHref(address.phone)
  const sellerTel = telHref(delivery.pickup.phone ?? '')
  const isOnTheWay = delivery.status === 'shipped'

  return (
    <Card className={styles.card}>
      <div className={styles.header}>
        <span className={styles.orderId}>#{delivery.order_id}</span>
        <span className={[styles.status, isOnTheWay ? styles.onTheWay : ''].join(' ')}>
          {t(`courier.status.${delivery.status}`)}
        </span>
      </div>

      {/* Collect first (Spec 10): from the seller, before the customer's door. */}
      <p className={styles.pickup}>
        {t('courier.pickup', { place: pickupPlace(delivery.pickup) })}
        {sellerTel && (
          <>
            {' · '}
            <a className={styles.phone} href={sellerTel}>
              {delivery.pickup.phone}
            </a>
          </>
        )}
      </p>
      <p className={styles.address}>
        {address.street}, {address.city} {address.postal_code}, {address.country}
      </p>
      {tel ? (
        <a className={styles.phone} href={tel}>
          {address.phone}
        </a>
      ) : (
        <p className={styles.address}>{address.phone}</p>
      )}
      {address.notes && (
        <p className={styles.notes}>
          <span className={styles.notesLabel}>{t('courier.notes')}: </span>
          {address.notes}
        </p>
      )}

      {delivery.cash_to_collect && (
        <p className={styles.cash}>
          {t('courier.cash', {
            total: formatMoney(delivery.cash_to_collect, delivery.currency ?? 'UZS', i18n.language),
          })}
        </p>
      )}

      <ul className={styles.items}>
        {delivery.items.map((item, index) => (
          <li key={index}>
            {item.name} × {item.qty}
          </li>
        ))}
      </ul>

      <PillButton
        variant="secondary"
        className={styles.action}
        onClick={() => openExternalLink(mapsUrl(delivery))}
      >
        {t('courier.actions.openMaps')}
      </PillButton>

      {isOnTheWay ? (
        <PillButton
          className={styles.action}
          disabled={isBusy}
          onClick={() => onDeliver(delivery.shipment_id)}
        >
          {delivery.cash_to_collect
            ? t('courier.actions.deliverCash')
            : t('courier.actions.deliver')}
        </PillButton>
      ) : (
        <>
          <PillButton
            className={styles.action}
            disabled={isBusy}
            onClick={() => onPickup(delivery.shipment_id)}
          >
            {t('courier.actions.pickup')}
          </PillButton>
          <PillButton
            variant="secondary"
            className={styles.action}
            disabled={isBusy}
            onClick={() => onRelease(delivery.shipment_id)}
          >
            {t('courier.actions.release')}
          </PillButton>
        </>
      )}
    </Card>
  )
}
