import { useTranslation } from 'react-i18next'

import { EmptyState } from './EmptyState'
import { PillButton } from './PillButton'

interface QueryErrorProps {
  onRetry: () => void
}

export function QueryError({ onRetry }: QueryErrorProps) {
  const { t } = useTranslation()

  return (
    <EmptyState
      title={t('common.error')}
      action={<PillButton onClick={onRetry}>{t('common.retry')}</PillButton>}
    />
  )
}
