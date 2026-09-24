import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { PillButton } from '../../../../shared/ui/PillButton'
import { createVariant, updateVariant } from '../../api'
import { adminErrorKey } from '../../errors'
import { useCatalogMutation } from '../../hooks'
import type { AdminAttribute, AdminVariant, VariantInput } from '../../types'
import { ErrorNote, Field } from '../ui'
import { inputClass } from '../inputClass'
import styles from './catalog.module.css'
import { isPrice, isStock } from './validation'

function attributeLabel(attribute: AdminAttribute, locale: string): string {
  return attribute.translations[locale]?.name ?? attribute.translations.en?.name ?? attribute.key
}

interface VariantRowProps {
  productId: number
  variant: AdminVariant | null
  attributes: AdminAttribute[]
  defaultPrice: string
}

function VariantRow({ productId, variant, attributes, defaultPrice }: VariantRowProps) {
  const { t, i18n } = useTranslation()
  const [form, setForm] = useState({
    sku: variant?.sku ?? '',
    price: variant?.price ?? defaultPrice,
    stock: String(variant?.stock_qty ?? 0),
    attributes: variant?.attribute_values ?? ({} as Record<string, string>),
  })
  const [invalid, setInvalid] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)
  const save = useCatalogMutation((input: VariantInput) =>
    variant ? updateVariant(variant.id, input) : createVariant(productId, input),
  )

  function set(patch: Partial<typeof form>) {
    setSaved(false)
    setForm((prev) => ({ ...prev, ...patch }))
  }

  function submit(event: FormEvent) {
    event.preventDefault()
    if (!isPrice(form.price)) return setInvalid(t('admin.catalog.invalidPrice'))
    if (!isStock(form.stock)) return setInvalid(t('admin.catalog.invalidStock'))
    setInvalid(null)
    const attributeValues = Object.fromEntries(
      Object.entries(form.attributes)
        .map(([key, value]) => [key, value.trim()])
        .filter(([, value]) => value !== ''),
    )
    save.mutate(
      {
        sku: form.sku.trim(),
        price: form.price.trim(),
        stock_qty: Number(form.stock),
        attribute_values: attributeValues,
      },
      {
        onSuccess: () => {
          setSaved(true)
          if (!variant) {
            setForm({ sku: '', price: defaultPrice, stock: '0', attributes: {} })
          }
        },
      },
    )
  }

  const label = variant ? variant.sku : t('admin.catalog.newVariant')

  return (
    <form className={styles.variant} onSubmit={submit} aria-label={label}>
      <Field label={t('admin.catalog.sku')}>
        {(id) => (
          <input
            id={id}
            required
            maxLength={64}
            className={inputClass}
            value={form.sku}
            onChange={(event) => set({ sku: event.target.value })}
          />
        )}
      </Field>
      <Field label={t('admin.catalog.price')}>
        {(id) => (
          <input
            id={id}
            required
            inputMode="decimal"
            className={inputClass}
            value={form.price}
            onChange={(event) => set({ price: event.target.value })}
          />
        )}
      </Field>
      <Field label={t('admin.catalog.stock')}>
        {(id) => (
          <input
            id={id}
            required
            inputMode="numeric"
            className={inputClass}
            value={form.stock}
            onChange={(event) => set({ stock: event.target.value })}
          />
        )}
      </Field>
      <PillButton type="submit" disabled={save.isPending}>
        {variant ? t('admin.common.save') : t('admin.common.add')}
      </PillButton>
      {attributes.map((attribute) => (
        <Field key={attribute.id} label={attributeLabel(attribute, i18n.language)}>
          {(id) => (
            <input
              id={id}
              className={inputClass}
              value={form.attributes[attribute.key] ?? ''}
              onChange={(event) =>
                set({ attributes: { ...form.attributes, [attribute.key]: event.target.value } })
              }
            />
          )}
        </Field>
      ))}
      {(invalid || save.error || saved) && (
        <div className={styles.variantWide}>
          <ErrorNote message={invalid ?? (save.error ? t(adminErrorKey(save.error)) : null)} />
          {saved && !invalid && !save.error && (
            <p className={styles.saved}>{t('admin.common.saved')}</p>
          )}
        </div>
      )}
    </form>
  )
}

interface VariantsEditorProps {
  productId: number
  variants: AdminVariant[]
  attributes: AdminAttribute[]
  defaultPrice: string
}

export function VariantsEditor({
  productId,
  variants,
  attributes,
  defaultPrice,
}: VariantsEditorProps) {
  const { t } = useTranslation()

  return (
    <div className={styles.section}>
      {variants.length === 0 && <p className={styles.muted}>{t('admin.catalog.noVariants')}</p>}
      {variants.map((variant) => (
        <VariantRow
          key={variant.id}
          productId={productId}
          variant={variant}
          attributes={attributes}
          defaultPrice={defaultPrice}
        />
      ))}
      <VariantRow
        productId={productId}
        variant={null}
        attributes={attributes}
        defaultPrice={defaultPrice}
      />
    </div>
  )
}
