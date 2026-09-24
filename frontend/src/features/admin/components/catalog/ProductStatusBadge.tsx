import { useTranslation } from 'react-i18next'

import type { ProductStatus } from '../../types'
import { Badge } from '../ui'

const TONE = { active: 'positive', draft: 'neutral', archived: 'warning' } as const

export function ProductStatusBadge({ status }: { status: ProductStatus }) {
  const { t } = useTranslation()
  return <Badge tone={TONE[status]}>{t(`admin.catalog.statuses.${status}`)}</Badge>
}
