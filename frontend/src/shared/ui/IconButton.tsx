import type { ButtonHTMLAttributes } from 'react'

import styles from './IconButton.module.css'

interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  'aria-label': string
}

export function IconButton({ className, ...rest }: IconButtonProps) {
  const classes = [styles.button, className].filter(Boolean).join(' ')
  return <button type="button" className={classes} {...rest} />
}
