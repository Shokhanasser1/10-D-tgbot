import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { Card } from '../../../shared/ui/Card'
import { PillButton } from '../../../shared/ui/PillButton'
import { QueryError } from '../../../shared/ui/QueryError'
import { Skeleton } from '../../../shared/ui/Skeleton'
import { createAttribute, createCategory, updateAttribute, updateCategory } from '../api'
import { inputClass } from '../components/inputClass'
import styles from '../components/catalog/catalog.module.css'
import { TranslationsEditor } from '../components/catalog/TranslationsEditor'
import { ErrorNote, Field, PageHeader } from '../components/ui'
import { adminErrorKey } from '../errors'
import { useAdminAttributes, useAdminCategories, useCatalogMutation } from '../hooks'
import type { AdminAttribute, AdminCategory, AttributeValueType } from '../types'
import layout from './CategoriesScreen.module.css'
import { EditGate } from '../components/EditGate'

const VALUE_TYPES: AttributeValueType[] = ['text', 'number', 'boolean', 'color']

function CategoryForm({ category }: { category: AdminCategory | null }) {
  const { t } = useTranslation()
  const [slug, setSlug] = useState(category?.slug ?? '')
  const [sortOrder, setSortOrder] = useState(String(category?.sort_order ?? 0))
  const save = useCatalogMutation((body: { slug: string; sort_order: number }) =>
    category ? updateCategory(category.id, body) : createCategory(body),
  )

  function submit(event: FormEvent) {
    event.preventDefault()
    save.mutate(
      { slug: slug.trim(), sort_order: Number(sortOrder) || 0 },
      {
        onSuccess: () => {
          if (!category) {
            setSlug('')
            setSortOrder('0')
          }
        },
      },
    )
  }

  return (
    <form className={styles.form} onSubmit={submit}>
      <div className={styles.grid}>
        <Field label={t('admin.catalog.slug')} hint={t('admin.catalog.slugHint')}>
          {(id) => (
            <input
              id={id}
              required
              maxLength={120}
              className={inputClass}
              value={slug}
              onChange={(event) => setSlug(event.target.value)}
            />
          )}
        </Field>
        <Field label={t('admin.catalog.sortOrder')}>
          {(id) => (
            <input
              id={id}
              type="number"
              className={inputClass}
              value={sortOrder}
              onChange={(event) => setSortOrder(event.target.value)}
            />
          )}
        </Field>
      </div>
      <ErrorNote message={save.error ? t(adminErrorKey(save.error)) : null} />
      <div className={styles.actions}>
        <PillButton type="submit" disabled={save.isPending}>
          {category ? t('admin.common.save') : t('admin.catalog.addCategory')}
        </PillButton>
      </div>
    </form>
  )
}

function AttributeForm({
  attribute,
  categories,
}: {
  attribute: AdminAttribute | null
  categories: AdminCategory[]
}) {
  const { t } = useTranslation()
  const [key, setKey] = useState(attribute?.key ?? '')
  const [categoryId, setCategoryId] = useState(String(attribute?.category_id ?? ''))
  const [valueType, setValueType] = useState<AttributeValueType>(attribute?.value_type ?? 'text')
  const save = useCatalogMutation(() =>
    attribute
      ? updateAttribute(attribute.id, { key: key.trim(), value_type: valueType })
      : createAttribute({
          key: key.trim(),
          category_id: Number(categoryId),
          value_type: valueType,
        }),
  )

  function submit(event: FormEvent) {
    event.preventDefault()
    save.mutate(undefined, { onSuccess: () => !attribute && setKey('') })
  }

  return (
    <form className={styles.form} onSubmit={submit}>
      <div className={styles.grid}>
        <Field label={t('admin.catalog.attributeKey')} hint={t('admin.catalog.attributeKeyHint')}>
          {(id) => (
            <input
              id={id}
              required
              maxLength={80}
              className={inputClass}
              value={key}
              onChange={(event) => setKey(event.target.value)}
            />
          )}
        </Field>
        {!attribute && (
          <Field label={t('admin.catalog.category')}>
            {(id) => (
              <select
                id={id}
                required
                className={inputClass}
                value={categoryId}
                onChange={(event) => setCategoryId(event.target.value)}
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
        )}
        <Field label={t('admin.catalog.valueType')}>
          {(id) => (
            <select
              id={id}
              className={inputClass}
              value={valueType}
              onChange={(event) => setValueType(event.target.value as AttributeValueType)}
            >
              {VALUE_TYPES.map((type) => (
                <option key={type} value={type}>
                  {t(`admin.catalog.valueTypes.${type}`)}
                </option>
              ))}
            </select>
          )}
        </Field>
      </div>
      <ErrorNote message={save.error ? t(adminErrorKey(save.error)) : null} />
      <div className={styles.actions}>
        <PillButton type="submit" disabled={save.isPending}>
          {attribute ? t('admin.common.save') : t('admin.catalog.addAttribute')}
        </PillButton>
      </div>
    </form>
  )
}

export function CategoriesScreen() {
  const { t, i18n } = useTranslation()
  const categories = useAdminCategories()
  const attributes = useAdminAttributes()

  if ((categories.isError && !categories.data) || (attributes.isError && !attributes.data)) {
    return (
      <QueryError
        onRetry={() => {
          void categories.refetch()
          void attributes.refetch()
        }}
      />
    )
  }
  if (!categories.data || !attributes.data) return <Skeleton height={240} />

  const nameField = [{ key: 'name', label: t('admin.catalog.name') }]

  return (
    <div className={layout.screen}>
      <Link to="/admin/catalog" className={layout.back}>
        ← {t('admin.catalog.backToProducts')}
      </Link>
      <PageHeader title={t('admin.catalog.categoriesAndAttributes')} />
      <EditGate permission="taxonomy.edit">
        <Card className={styles.section}>
          <h2 className={styles.sectionTitle}>{t('admin.catalog.categories')}</h2>
          {categories.data.map((category) => (
            <details key={category.id} className={layout.item}>
              <summary className={layout.summary}>
                <span>{category.name}</span>
                <span className={styles.muted}>{category.slug}</span>
              </summary>
              <div className={layout.body}>
                <CategoryForm category={category} />
                <TranslationsEditor
                  entityType="category"
                  entityId={category.id}
                  translations={category.translations}
                  fields={nameField}
                />
              </div>
            </details>
          ))}
          <h3 className={layout.subTitle}>{t('admin.catalog.addCategory')}</h3>
          <CategoryForm category={null} />
        </Card>

        <Card className={styles.section}>
          <h2 className={styles.sectionTitle}>{t('admin.catalog.attributes')}</h2>
          <p className={styles.muted}>{t('admin.catalog.attributesHint')}</p>
          {attributes.data.map((attribute) => {
            const category = categories.data.find((c) => c.id === attribute.category_id)
            const label =
              attribute.translations[i18n.language]?.name ??
              attribute.translations.en?.name ??
              attribute.key
            return (
              <details key={attribute.id} className={layout.item}>
                <summary className={layout.summary}>
                  <span>{label}</span>
                  <span className={styles.muted}>
                    {attribute.key} · {category?.name ?? '—'}
                  </span>
                </summary>
                <div className={layout.body}>
                  <AttributeForm attribute={attribute} categories={categories.data} />
                  <TranslationsEditor
                    entityType="attribute"
                    entityId={attribute.id}
                    translations={attribute.translations}
                    fields={nameField}
                  />
                </div>
              </details>
            )
          })}
          <h3 className={layout.subTitle}>{t('admin.catalog.addAttribute')}</h3>
          <AttributeForm attribute={null} categories={categories.data} />
        </Card>
      </EditGate>
    </div>
  )
}
