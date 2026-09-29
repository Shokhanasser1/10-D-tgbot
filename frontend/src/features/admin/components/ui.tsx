import { type ReactNode, useEffect, useId, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { PillButton } from '../../../shared/ui/PillButton'
import styles from './ui.module.css'

export function PageHeader({ title, actions }: { title: string; actions?: ReactNode }) {
  return (
    <div className={styles.pageHeader}>
      <h1 className={styles.pageTitle}>{title}</h1>
      {actions && <div className={styles.pageActions}>{actions}</div>}
    </div>
  )
}

export function ErrorNote({ message }: { message: string | null }) {
  if (!message) return null
  return (
    <p role="alert" className={styles.error}>
      {message}
    </p>
  )
}

type Tone = 'neutral' | 'positive' | 'warning' | 'negative'

export function Badge({ tone = 'neutral', children }: { tone?: Tone; children: ReactNode }) {
  return <span className={[styles.badge, styles[tone]].join(' ')}>{children}</span>
}

interface FieldProps {
  label: string
  children: (id: string) => ReactNode
  hint?: string
}

/** A labelled form control; `children` receives the id to put on the control. */
export function Field({ label, children, hint }: FieldProps) {
  const id = useId()
  return (
    <div className={styles.field}>
      <label htmlFor={id} className={styles.label}>
        {label}
      </label>
      {children(id)}
      {hint && <span className={styles.hint}>{hint}</span>}
    </div>
  )
}

interface ConfirmDialogProps {
  open: boolean
  title: string
  message?: string
  confirmLabel: string
  /** When set, the dialog asks for a text (e.g. a reason) and requires it. */
  inputLabel?: string
  /** A password field instead of a text area; its value is passed on untrimmed. */
  password?: boolean
  maxLength?: number
  busy?: boolean
  error?: string | null
  onConfirm: (text: string) => void
  onCancel: () => void
}

export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel,
  inputLabel,
  password = false,
  maxLength = 500,
  busy = false,
  error = null,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const { t } = useTranslation()
  const dialog = useRef<HTMLDialogElement>(null)
  const [text, setText] = useState('')
  const inputId = useId()

  useEffect(() => {
    const node = dialog.current
    if (!node) return
    if (open && !node.open) {
      setText('')
      // jsdom has no showModal; the open attribute is enough there.
      if (typeof node.showModal === 'function') node.showModal()
      else node.setAttribute('open', '')
    } else if (!open && node.open) {
      if (typeof node.close === 'function') node.close()
      else node.removeAttribute('open')
    }
  }, [open])

  const needsText = inputLabel !== undefined
  const disabled = busy || (needsText && text.trim() === '')

  return (
    <dialog
      ref={dialog}
      className={styles.dialog}
      aria-labelledby={`${inputId}-title`}
      onCancel={(event) => {
        event.preventDefault()
        onCancel()
      }}
    >
      <form
        method="dialog"
        className={styles.dialogBody}
        onSubmit={(event) => {
          event.preventDefault()
          if (!disabled) onConfirm(password ? text : text.trim())
        }}
      >
        <h2 id={`${inputId}-title`} className={styles.dialogTitle}>
          {title}
        </h2>
        {message && <p className={styles.dialogText}>{message}</p>}
        {needsText && (
          <div className={styles.field}>
            <label htmlFor={inputId} className={styles.label}>
              {inputLabel}
            </label>
            {password ? (
              <input
                id={inputId}
                type="password"
                autoComplete="current-password"
                className={styles.input}
                value={text}
                maxLength={200}
                onChange={(event) => setText(event.target.value)}
              />
            ) : (
              <textarea
                id={inputId}
                className={styles.input}
                value={text}
                maxLength={maxLength}
                rows={3}
                onChange={(event) => setText(event.target.value)}
              />
            )}
          </div>
        )}
        <ErrorNote message={error} />
        <div className={styles.dialogActions}>
          <PillButton variant="secondary" onClick={onCancel} disabled={busy}>
            {t('admin.common.back')}
          </PillButton>
          <PillButton type="submit" disabled={disabled} className={styles.danger}>
            {confirmLabel}
          </PillButton>
        </div>
      </form>
    </dialog>
  )
}
