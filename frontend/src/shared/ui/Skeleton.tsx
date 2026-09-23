import type { CSSProperties } from 'react'

import styles from './Skeleton.module.css'

interface SkeletonProps {
  width?: string | number
  height?: string | number
  radius?: string
  className?: string
}

export function Skeleton({ width = '100%', height = '16px', radius, className }: SkeletonProps) {
  const style: CSSProperties = { width, height, borderRadius: radius }
  const classes = [styles.skeleton, className].filter(Boolean).join(' ')
  return <div className={classes} style={style} />
}
