import { describe, expect, it } from 'vitest'

import en from './locales/en.json'
import ru from './locales/ru.json'
import uz from './locales/uz.json'

type Tree = { [key: string]: string | Tree }

const PLURAL_SUFFIX = /_(zero|one|two|few|many|other)$/

/** "a.b.c" -> template, with plural forms of one key folded into a single entry. */
function flatten(tree: Tree, prefix = ''): Map<string, string[]> {
  const result = new Map<string, string[]>()
  for (const [key, value] of Object.entries(tree)) {
    const path = prefix + key
    if (typeof value === 'string') {
      const base = path.replace(PLURAL_SUFFIX, '')
      result.set(base, [...(result.get(base) ?? []), value])
    } else {
      for (const [nested, templates] of flatten(value, `${path}.`)) {
        result.set(nested, [...(result.get(nested) ?? []), ...templates])
      }
    }
  }
  return result
}

/** The {{placeholders}} a set of templates uses, ignoring `count`, which i18next supplies. */
function placeholders(templates: string[]): string[] {
  const names = new Set<string>()
  for (const template of templates) {
    for (const match of template.matchAll(/\{\{\s*(\w+)\s*\}\}/g)) names.add(match[1])
  }
  names.delete('count')
  return [...names].sort()
}

const locales = { en: flatten(en), ru: flatten(ru), uz: flatten(uz) }

describe('translations', () => {
  it.each(['ru', 'uz'] as const)('%s has exactly the keys English has', (name) => {
    const english = [...locales.en.keys()].sort()
    const other = [...locales[name].keys()].sort()

    // A missing translation would fall back to English silently; an extra one is dead text.
    expect(other.filter((key) => !english.includes(key))).toEqual([])
    expect(english.filter((key) => !other.includes(key))).toEqual([])
  })

  it.each(['ru', 'uz'] as const)('%s uses the same {{placeholders}} as English', (name) => {
    const mismatched = [...locales.en].filter(
      ([key, templates]) =>
        JSON.stringify(placeholders(templates)) !==
        JSON.stringify(placeholders(locales[name].get(key) ?? [])),
    )

    expect(mismatched.map(([key]) => key)).toEqual([])
  })

  it.each(['en', 'ru', 'uz'] as const)('%s has no empty strings', (name) => {
    const empty = [...locales[name]].filter(([, templates]) =>
      templates.some((t) => t.trim() === ''),
    )

    expect(empty.map(([key]) => key)).toEqual([])
  })

  // Order and timeline labels sit side by side on one screen; identical text would read as a
  // duplicate (and makes `getByText` ambiguous).
  it.each(['en', 'ru', 'uz'] as const)(
    '%s timeline labels differ from order status labels',
    (name) => {
      const tree = { en, ru, uz }[name]
      const statuses = Object.values(tree.orders.status)
      const steps = Object.values(tree.tracking.steps)

      expect(steps.filter((label) => statuses.includes(label))).toEqual([])
    },
  )
})
