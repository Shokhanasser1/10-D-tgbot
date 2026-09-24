import { useTranslation } from 'react-i18next'

import { openTelegramLink } from '../../../shared/telegram/webApp'
import { formatAgo, secondsSince } from '../../../shared/time/formatAgo'
import { useNow } from '../../../shared/time/useNow'
import { Card } from '../../../shared/ui/Card'
import { PillButton } from '../../../shared/ui/PillButton'
import styles from './GpsPanel.module.css'

interface GpsPanelProps {
  botUsername: string | null
  locationUpdatedAt: string | null
}

/**
 * Telegram Mini Apps cannot read GPS in the background, so the courier shares a Live Location
 * in the bot chat and the bot's webhook receives it. This panel walks them through that and
 * shows whether it is actually arriving.
 */
export function GpsPanel({ botUsername, locationUpdatedAt }: GpsPanelProps) {
  const { t } = useTranslation()
  const now = useNow(1000)

  return (
    <Card className={styles.panel}>
      <h2 className={styles.title}>{t('courier.gps.title')}</h2>
      <p className={styles.text}>{t('courier.gps.instructions')}</p>
      {botUsername && (
        <PillButton
          variant="secondary"
          className={styles.action}
          onClick={() => openTelegramLink(`https://t.me/${botUsername}`)}
        >
          {t('courier.gps.openBot')}
        </PillButton>
      )}
      <p role="status" className={styles.status}>
        {locationUpdatedAt
          ? t('courier.gps.updated', { ago: formatAgo(t, secondsSince(locationUpdatedAt, now)) })
          : t('courier.gps.none')}
      </p>
    </Card>
  )
}
