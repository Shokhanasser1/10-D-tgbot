import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { PillButton } from '../../../../shared/ui/PillButton'
import type { AdminCategory, ProductInput, ProductStatus } from '../../types'
import { ErrorNote, Field } from '../ui'
import { inputClass } from '../inputClass'
import styles from './catalog.module.css'
import { isPrice } from './validation'

const STATUSES: ProductStatus[] = ['draft', 'active', 'archived']

interface ProductBasicsFormProps {
  initial?: ProductInput
  categories: AdminCategory[]
  submitLabel: string
  busy: boolean
  error: string | null
  onSubmit: (input: ProductInput) => void
}

export function ProductBasicsForm({
  initial,
  categories,
  submitLabel,
  busy,
  error,
  onSubmit,
}: ProductBasicsFormProps) {
  const { t } = useTranslation()
  const [form, setForm] = useState({
    category_id: initial ? String(initial.category_id) : '',
    base_sku: initial?.base_sku ?? '',
    base_price: initial?.base_price ?? '',
    status: initial?.status ?? ('draft' as ProductStatus),
  })
  const [invalid, setInvalid] = useState<string | null>(null)

  function set<K extends keyof typeof form>(key: K, value: (typeof form)[K]) {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  function submit(event: FormEvent) {
    event.preventDefault()
    if (!isPrice(form.base_price)) {
      setInvalid(t('admin.catalog.invalidPrice'))
      return
    }
    setInvalid(null)
    onSubmit({
      category_id: Number(form.category_id),
      base_sku: form.base_sku.trim(),
      base_price: form.base_price.trim(),
      status: form.status,
    })
  }

  return (
    <form className={styles.form} onSubmit={submit}>
      <div className={styles.grid}>
        <Field label={t('admin.catalog.category')}>
          {(id) => (
            <select
              id={id}
              required
              className={inputClass}
              value={form.category_id}
              onChange={(event) => set('category_id', event.target.value)}
            >
              <option value="" disabled>
                {t('admin.catalog.chooseCategory')}
              </option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          )}
        </Field>
        <Field label={t('admin.catalog.status')}>
          {(id) => (
            <select
              id={id}
              className={inputClass}
              value={form.status}
              onChange={(event) => set('status', event.target.value as ProductStatus)}
            >
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {t(`admin.catalog.statuses.${s}`)}
                </option>
              ))}
            </select>
          )}
        </Field>
        <Field label={t('admin.catalog.sku')}>
          {(id) => (
            <input
              id={id}
              required
              maxLength={64}
              className={inputClass}
              value={form.base_sku}
              onChange={(event) => set('base_sku', event.target.value)}
            />
          )}
        </Field>
        <Field label={t('admin.catalog.basePrice')}>
          {(id) => (
            <input
              id={id}
              required
              inputMode="decimal"
              className={inputClass}
              value={form.base_price}
              onChange={(event) => set('base_price', event.target.value)}
            />
          )}
        </Field>
      </div>
      <ErrorNote message={invalid ?? error} />
      <div className={styles.actions}>
        <PillButton type="submit" disabled={busy}>
          {submitLabel}
        </PillButton>
      </div>
    </form>
  )
}
