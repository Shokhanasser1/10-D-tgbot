import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { Card } from '../../../shared/ui/Card'
import { EmptyState } from '../../../shared/ui/EmptyState'
import { PillButton } from '../../../shared/ui/PillButton'
import { QueryError } from '../../../shared/ui/QueryError'
import { Skeleton } from '../../../shared/ui/Skeleton'
import { createSeller, updateSeller } from '../api'
import { inputClass } from '../components/inputClass'
import { Badge, ConfirmDialog, ErrorNote, Field, PageHeader } from '../components/ui'
import { adminErrorKey } from '../errors'
import { formatMoney, formatPercent } from '../format'
import { useAdminSellers, useSellerMutation } from '../hooks'
import { useCan } from '../meContext'
import type { AdminSeller } from '../types'
import styles from './SellersScreen.module.css'

const EMPTY_FORM = {
  name: '',
  phone: '',
  pickupAddress: '',
  telegramId: '',
  personName: '',
  commission: '10',
}

/** The platform's share of the goods, 0..100 (Spec 11). */
function CommissionField({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const { t } = useTranslation()
  return (
    <Field label={t('admin.sellers.commission')} hint={t('admin.sellers.commissionHint')}>
      {(id) => (
        <input
          id={id}
          required
          type="number"
          min={0}
          max={100}
          step="0.01"
          className={inputClass}
          value={value}
          onChange={(event) => onChange(event.target.value)}
        />
      )}
    </Field>
  )
}

/** The seller and the person who will sign in for it, added together (Spec 9 §5). */
function AddSellerForm() {
  const { t } = useTranslation()
  const [form, setForm] = useState(EMPTY_FORM)
  const add = useSellerMutation(createSeller)

  function set(key: keyof typeof EMPTY_FORM, value: string) {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  function submit(event: FormEvent) {
    event.preventDefault()
    add.mutate(
      {
        name: form.name.trim(),
        phone: form.phone.trim() || null,
        pickup_address: form.pickupAddress.trim(),
        telegram_id: Number(form.telegramId),
        display_name: form.personName.trim(),
        commission_percent: form.commission.trim(),
      },
      { onSuccess: () => setForm(EMPTY_FORM) },
    )
  }

  return (
    <form className={styles.form} onSubmit={submit}>
      <h2 className={styles.cardTitle}>{t('admin.sellers.add')}</h2>
      <div className={styles.grid}>
        <Field label={t('admin.sellers.name')} hint={t('admin.sellers.nameHint')}>
          {(id) => (
            <input
              id={id}
              required
              maxLength={100}
              className={inputClass}
              value={form.name}
              onChange={(event) => set('name', event.target.value)}
            />
          )}
        </Field>
        <Field label={t('admin.sellers.phone')}>
          {(id) => (
            <input
              id={id}
              type="tel"
              maxLength={32}
              className={inputClass}
              value={form.phone}
              onChange={(event) => set('phone', event.target.value)}
            />
          )}
        </Field>
        <Field label={t('admin.sellers.pickupAddress')} hint={t('admin.sellers.pickupAddressHint')}>
          {(id) => (
            <input
              id={id}
              required
              maxLength={500}
              className={inputClass}
              value={form.pickupAddress}
              onChange={(event) => set('pickupAddress', event.target.value)}
            />
          )}
        </Field>
        <Field label={t('admin.common.telegramId')} hint={t('admin.common.telegramIdHint')}>
          {(id) => (
            <input
              id={id}
              required
              inputMode="numeric"
              pattern="[0-9]+"
              className={inputClass}
              value={form.telegramId}
              onChange={(event) => set('telegramId', event.target.value)}
            />
          )}
        </Field>
        <Field label={t('admin.sellers.personName')} hint={t('admin.sellers.personNameHint')}>
          {(id) => (
            <input
              id={id}
              required
              maxLength={100}
              className={inputClass}
              value={form.personName}
              onChange={(event) => set('personName', event.target.value)}
            />
          )}
        </Field>
        <CommissionField value={form.commission} onChange={(v) => set('commission', v)} />
      </div>
      <ErrorNote message={add.error ? t(adminErrorKey(add.error)) : null} />
      <div className={styles.formActions}>
        <PillButton type="submit" disabled={add.isPending}>
          {t('admin.common.add')}
        </PillButton>
      </div>
    </form>
  )
}

function EditSellerForm({ seller, onDone }: { seller: AdminSeller; onDone: () => void }) {
  const { t } = useTranslation()
  const [form, setForm] = useState({
    name: seller.name,
    phone: seller.phone ?? '',
    pickupAddress: seller.pickup_address ?? '',
    commission: formatPercent(seller.commission_percent),
  })
  const save = useSellerMutation(() =>
    updateSeller(seller.id, {
      name: form.name.trim(),
      phone: form.phone.trim() || null,
      pickup_address: form.pickupAddress.trim(),
      commission_percent: form.commission.trim(),
    }),
  )

  function submit(event: FormEvent) {
    event.preventDefault()
    save.mutate(undefined, { onSuccess: onDone })
  }

  return (
    <form className={[styles.form, styles.editForm].join(' ')} onSubmit={submit}>
      <div className={styles.grid}>
        <Field label={t('admin.sellers.name')}>
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
        <Field label={t('admin.sellers.phone')}>
          {(id) => (
            <input
              id={id}
              type="tel"
              maxLength={32}
              className={inputClass}
              value={form.phone}
              onChange={(event) => setForm({ ...form, phone: event.target.value })}
            />
          )}
        </Field>
        <Field label={t('admin.sellers.pickupAddress')}>
          {(id) => (
            <input
              id={id}
              required
              maxLength={500}
              className={inputClass}
              value={form.pickupAddress}
              onChange={(event) => setForm({ ...form, pickupAddress: event.target.value })}
            />
          )}
        </Field>
        <CommissionField
          value={form.commission}
          onChange={(v) => setForm({ ...form, commission: v })}
        />
      </div>
      <ErrorNote message={save.error ? t(adminErrorKey(save.error)) : null} />
      <div className={styles.formActions}>
        <PillButton type="button" variant="secondary" className={styles.small} onClick={onDone}>
          {t('admin.sellers.cancel')}
        </PillButton>
        <PillButton type="submit" className={styles.small} disabled={save.isPending}>
          {t('admin.common.save')}
        </PillButton>
      </div>
    </form>
  )
}

export function SellersScreen() {
  const { t, i18n } = useTranslation()
  // An accountant opens this list for the money only (Spec 11).
  const canManage = useCan('sellers.manage')
  const canPayOut = useCan('payouts.manage')
  const query = useAdminSellers()
  const [editing, setEditing] = useState<number | null>(null)
  const [toDeactivate, setToDeactivate] = useState<AdminSeller | null>(null)
  const toggle = useSellerMutation(({ id, active }: { id: number; active: boolean }) =>
    updateSeller(id, { is_active: active }),
  )

  return (
    <div className={styles.screen}>
      <PageHeader title={t('admin.nav.sellers')} />
      {canManage && (
        <Card>
          <AddSellerForm />
        </Card>
      )}
      {query.isError && !query.data && <QueryError onRetry={() => query.refetch()} />}
      {query.isLoading && <Skeleton height={160} />}
      {query.data?.length === 0 && <EmptyState title={t('admin.sellers.empty')} />}
      <ul className={styles.list}>
        {query.data?.map((seller) => (
          <li key={seller.id} className={styles.row}>
            <span className={styles.main}>
              <span className={styles.name}>{seller.name}</span>
              <span className={styles.muted}>
                {seller.pickup_address ?? t('admin.sellers.noAddress')}
                {seller.phone && ` · ${seller.phone}`}
              </span>
              {seller.accounts.map((account) => (
                <span key={account.id} className={styles.muted}>
                  {account.display_name} · {account.telegram_id}
                </span>
              ))}
              <span className={styles.muted}>
                {t('admin.sellers.commissionShort', {
                  percent: formatPercent(seller.commission_percent),
                })}
                {seller.balances.map((b) => (
                  <span key={b.currency}>
                    {' · '}
                    {t('admin.sellers.owed', {
                      amount: formatMoney(b.balance, b.currency, i18n.language),
                    })}
                  </span>
                ))}
              </span>
            </span>
            <Badge>{t('admin.sellers.products', { count: seller.product_count })}</Badge>
            {!seller.is_active && <Badge tone="warning">{t('admin.sellers.inactive')}</Badge>}
            {canPayOut && (
              <Link to={`/admin/sellers/${seller.id}`} className={styles.small}>
                {t('admin.sellers.openLedger')}
              </Link>
            )}
            {canManage && (
              <PillButton
                variant="secondary"
                className={styles.small}
                onClick={() => setEditing(editing === seller.id ? null : seller.id)}
              >
                {t('admin.sellers.edit')}
              </PillButton>
            )}
            {!canManage ? null : seller.is_active ? (
              <PillButton
                variant="secondary"
                className={styles.small}
                disabled={toggle.isPending}
                onClick={() => setToDeactivate(seller)}
              >
                {t('admin.common.deactivate')}
              </PillButton>
            ) : (
              <PillButton
                variant="secondary"
                className={styles.small}
                disabled={toggle.isPending}
                onClick={() => toggle.mutate({ id: seller.id, active: true })}
              >
                {t('admin.common.activate')}
              </PillButton>
            )}
            {editing === seller.id && (
              <EditSellerForm seller={seller} onDone={() => setEditing(null)} />
            )}
          </li>
        ))}
      </ul>
      <ConfirmDialog
        open={toDeactivate !== null}
        title={t('admin.sellers.deactivateTitle', { name: toDeactivate?.name ?? '' })}
        message={t('admin.sellers.deactivateMessage')}
        confirmLabel={t('admin.common.deactivate')}
        busy={toggle.isPending}
        error={toggle.error ? t(adminErrorKey(toggle.error)) : null}
        onCancel={() => {
          toggle.reset()
          setToDeactivate(null)
        }}
        onConfirm={() =>
          toDeactivate &&
          toggle.mutate(
            { id: toDeactivate.id, active: false },
            { onSuccess: () => setToDeactivate(null) },
          )
        }
      />
    </div>
  )
}
