import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { SUPPORTED_LOCALES, type SupportedLocale } from '../../../../shared/i18n'
import { PillButton } from '../../../../shared/ui/PillButton'
import { upsertTranslation } from '../../api'
import { adminErrorKey } from '../../errors'
import { useCatalogMutation } from '../../hooks'
import type { TranslationInput, Translations } from '../../types'
import { ErrorNote, Field } from '../ui'
import { inputClass } from '../inputClass'
import styles from './catalog.module.css'

interface TranslatedField {
  key: string
  label: string
  multiline?: boolean
}

interface TranslationsEditorProps {
  entityType: TranslationInput['entity_type']
  entityId: number
  fields: TranslatedField[]
  translations: Translations
}

/** Per-language texts. Only filled-in values that changed are sent (the API upserts them). */
export function TranslationsEditor({
  entityType,
  entityId,
  fields,
  translations,
}: TranslationsEditorProps) {
  const { t } = useTranslation()
  const [locale, setLocale] = useState<SupportedLocale>('en')
  const [draft, setDraft] = useState<Translations>(translations)
  const [saved, setSaved] = useState(false)
  const save = useCatalogMutation((changes: TranslationInput[]) =>
    Promise.all(changes.map(upsertTranslation)),
  )

  function valueOf(loc: string, field: string, source: Translations = draft): string {
    return source[loc]?.[field] ?? ''
  }

  function change(field: string, value: string) {
    setSaved(false)
    setDraft((prev) => ({ ...prev, [locale]: { ...prev[locale], [field]: value } }))
  }

  function submit(event: FormEvent) {
    event.preventDefault()
    const changes: TranslationInput[] = []
    for (const loc of SUPPORTED_LOCALES) {
      for (const { key } of fields) {
        const value = valueOf(loc, key).trim()
        if (value && value !== valueOf(loc, key, translations)) {
          changes.push({
            entity_type: entityType,
            entity_id: entityId,
            locale: loc,
            field: key,
            value,
          })
        }
      }
    }
    if (changes.length === 0) return
    save.mutate(changes, { onSuccess: () => setSaved(true) })
  }

  return (
    <form className={styles.form} onSubmit={submit}>
      <div role="tablist" aria-label={t('admin.catalog.language')} className={styles.tabs}>
        {SUPPORTED_LOCALES.map((loc) => (
          <button
            key={loc}
            type="button"
            role="tab"
            aria-selected={loc === locale}
            className={[styles.tab, loc === locale ? styles.activeTab : ''].join(' ')}
            onClick={() => setLocale(loc)}
          >
            {loc.toUpperCase()}
            {fields.some(({ key }) => !valueOf(loc, key)) ? ' •' : ''}
          </button>
        ))}
      </div>
      {fields.map(({ key, label, multiline }) => (
        <Field key={`${locale}-${key}`} label={`${label} (${locale.toUpperCase()})`}>
          {(id) =>
            multiline ? (
              <textarea
                id={id}
                rows={4}
                className={inputClass}
                value={valueOf(locale, key)}
                onChange={(event) => change(key, event.target.value)}
              />
            ) : (
              <input
                id={id}
                className={inputClass}
                value={valueOf(locale, key)}
                onChange={(event) => change(key, event.target.value)}
              />
            )
          }
        </Field>
      ))}
      <p className={styles.muted}>{t('admin.catalog.translationsHint')}</p>
      <ErrorNote message={save.error ? t(adminErrorKey(save.error)) : null} />
      <div className={styles.actions}>
        {saved && <p className={styles.saved}>{t('admin.common.saved')}</p>}
        <PillButton type="submit" disabled={save.isPending}>
          {t('admin.common.save')}
        </PillButton>
      </div>
    </form>
  )
}
