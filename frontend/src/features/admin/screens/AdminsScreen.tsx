import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { Card } from '../../../shared/ui/Card'
import { PillButton } from '../../../shared/ui/PillButton'
import { QueryError } from '../../../shared/ui/QueryError'
import { Skeleton } from '../../../shared/ui/Skeleton'
import { createAdmin, updateAdmin } from '../api'
import { Badge, ConfirmDialog, ErrorNote, Field, PageHeader } from '../components/ui'
import { adminErrorKey } from '../errors'
import { useAdmins, useAdminsMutation } from '../hooks'
import type { Admin, AdminRole } from '../types'
import { inputClass } from '../components/inputClass'
import styles from './CouriersScreen.module.css'

const ROLES: AdminRole[] = ['owner', 'catalog_manager', 'dispatcher']

function RoleSelect({
  value,
  onChange,
  id,
  disabled,
  label,
}: {
  value: AdminRole
  onChange: (role: AdminRole) => void
  id?: string
  disabled?: boolean
  label?: string
}) {
  const { t } = useTranslation()
  return (
    <select
      id={id}
      aria-label={label}
      className={inputClass}
      value={value}
      disabled={disabled}
      onChange={(event) => onChange(event.target.value as AdminRole)}
    >
      {ROLES.map((role) => (
        <option key={role} value={role}>
          {t(`admin.roles.${role}`)}
        </option>
      ))}
    </select>
  )
}

function AddAdminForm() {
  const { t } = useTranslation()
  const [form, setForm] = useState({
    telegramId: '',
    name: '',
    role: 'dispatcher' as AdminRole,
  })
  const add = useAdminsMutation(createAdmin)

  function submit(event: FormEvent) {
    event.preventDefault()
    add.mutate(
      { telegram_id: Number(form.telegramId), display_name: form.name.trim(), role: form.role },
      { onSuccess: () => setForm({ telegramId: '', name: '', role: 'dispatcher' }) },
    )
  }

  return (
    <form className={styles.form} onSubmit={submit}>
      <h2 className={styles.cardTitle}>{t('admin.admins.add')}</h2>
      <div className={styles.grid}>
        <Field label={t('admin.common.telegramId')} hint={t('admin.common.telegramIdHint')}>
          {(id) => (
            <input
              id={id}
              required
              inputMode="numeric"
              pattern="[0-9]+"
              className={inputClass}
              value={form.telegramId}
              onChange={(event) => setForm({ ...form, telegramId: event.target.value })}
            />
          )}
        </Field>
        <Field label={t('admin.admins.name')}>
          {(id) => (
            <input
              id={id}
              required
              maxLength={100}
              className={inputClass}
              value={form.name}
              onChange={(event) => setForm({ ...form, name: event.target.value })}
            />
          )}
        </Field>
        <Field label={t('admin.admins.role')}>
          {(id) => (
            <RoleSelect id={id} value={form.role} onChange={(role) => setForm({ ...form, role })} />
          )}
        </Field>
      </div>
      <p className={styles.muted}>{t('admin.admins.rolesHint')}</p>
      <ErrorNote message={add.error ? t(adminErrorKey(add.error)) : null} />
      <div className={styles.formActions}>
        <PillButton type="submit" disabled={add.isPending}>
          {t('admin.common.add')}
        </PillButton>
      </div>
    </form>
  )
}

export function AdminsScreen({ currentTelegramId }: { currentTelegramId: number | null }) {
  const { t } = useTranslation()
  const query = useAdmins()
  const [toDeactivate, setToDeactivate] = useState<Admin | null>(null)
  const change = useAdminsMutation(
    ({ id, ...body }: { id: number } & Partial<Pick<Admin, 'role' | 'is_active'>>) =>
      updateAdmin(id, body),
  )

  return (
    <div className={styles.screen}>
      <PageHeader title={t('admin.nav.admins')} />
      <Card>
        <AddAdminForm />
      </Card>
      {query.isError && !query.data && <QueryError onRetry={() => query.refetch()} />}
      {query.isLoading && <Skeleton height={160} />}
      <ErrorNote message={change.error && !toDeactivate ? t(adminErrorKey(change.error)) : null} />
      <ul className={styles.list}>
        {query.data?.map((admin) => {
          const isMe = admin.telegram_id === currentTelegramId
          return (
            <li key={admin.id} className={styles.row}>
              <span className={styles.main}>
                <span className={styles.name}>
                  {admin.display_name}
                  {isMe && ` (${t('admin.admins.you')})`}
                </span>
                <span className={styles.muted}>{admin.telegram_id}</span>
              </span>
              {!admin.is_active && <Badge tone="warning">{t('admin.admins.inactive')}</Badge>}
              <div>
                <RoleSelect
                  label={t('admin.admins.roleOf', { name: admin.display_name })}
                  value={admin.role}
                  disabled={change.isPending}
                  onChange={(role) => change.mutate({ id: admin.id, role })}
                />
              </div>
              {admin.is_active ? (
                <PillButton
                  variant="secondary"
                  className={styles.small}
                  disabled={change.isPending || isMe}
                  onClick={() => setToDeactivate(admin)}
                >
                  {t('admin.common.deactivate')}
                </PillButton>
              ) : (
                <PillButton
                  variant="secondary"
                  className={styles.small}
                  disabled={change.isPending}
                  onClick={() => change.mutate({ id: admin.id, is_active: true })}
                >
                  {t('admin.common.activate')}
                </PillButton>
              )}
            </li>
          )
        })}
      </ul>
      <ConfirmDialog
        open={toDeactivate !== null}
        title={t('admin.admins.deactivateTitle', { name: toDeactivate?.display_name ?? '' })}
        message={t('admin.admins.deactivateMessage')}
        confirmLabel={t('admin.common.deactivate')}
        busy={change.isPending}
        error={change.error ? t(adminErrorKey(change.error)) : null}
        onCancel={() => {
          change.reset()
          setToDeactivate(null)
        }}
        onConfirm={() =>
          toDeactivate &&
          change.mutate(
            { id: toDeactivate.id, is_active: false },
            { onSuccess: () => setToDeactivate(null) },
          )
        }
      />
    </div>
  )
}
