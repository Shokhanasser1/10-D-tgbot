import { isTelegramEnv } from '../telegram/webApp'
import { PillButton } from './PillButton'
import styles from './ActionBar.module.css'

interface ActionBarProps {
  label: string
  onClick: () => void
  disabled?: boolean
}

/**
 * Fallback for the Telegram native MainButton when previewing outside Telegram
 * (local browser dev). Renders nothing inside a real Telegram WebView, where the
 * corresponding useMainButton() hook already provides this action.
 */
export function ActionBar({ label, onClick, disabled }: ActionBarProps) {
  if (isTelegramEnv()) return null

  return (
    <div className={styles.bar}>
      <PillButton className={styles.button} onClick={onClick} disabled={disabled}>
        {label}
      </PillButton>
    </div>
  )
}
