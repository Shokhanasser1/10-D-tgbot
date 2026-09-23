import type { ButtonHTMLAttributes } from 'react'

import styles from './PillButton.module.css'

interface PillButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary'
}

export function PillButton({ variant = 'primary', className, ...rest }: PillButtonProps) {
  const classes = [styles.button, styles[variant], className].filter(Boolean).join(' ')
  return <button type="button" className={classes} {...rest} />
}
