import { useTranslation } from 'react-i18next'

import type { ShipmentStatus } from '../types'
import styles from './TrackingTimeline.module.css'

const STEPS = ['paid', 'assigned', 'shipped', 'delivered'] as const

// Where each shipment status sits on the timeline. A paid order with no shipment yet, and one
// still waiting for a courier, are both on the first step.
const STEP_INDEX: Record<ShipmentStatus, number> = {
  processing: 0,
  assigned: 1,
  shipped: 2,
  delivered: 3,
}

interface TrackingTimelineProps {
  status: ShipmentStatus | null
}

export function TrackingTimeline({ status }: TrackingTimelineProps) {
  const { t } = useTranslation()
  const reached = status === null ? 0 : STEP_INDEX[status]

  return (
    <ol className={styles.timeline}>
      {STEPS.map((step, index) => (
        <li
          key={step}
          aria-current={index === reached ? 'step' : undefined}
          className={[
            styles.step,
            index <= reached ? styles.done : '',
            index === reached ? styles.current : '',
          ].join(' ')}
        >
          <span className={styles.dot} aria-hidden="true" />
          <span className={styles.label}>{t(`tracking.steps.${step}`)}</span>
        </li>
      ))}
    </ol>
  )
}
