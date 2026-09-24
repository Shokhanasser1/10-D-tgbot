import { describe, expect, it } from 'vitest'

import i18n from '../i18n'
import { formatAgo, secondsSince } from './formatAgo'

describe('secondsSince', () => {
  const now = Date.parse('2026-09-24T12:00:00Z')

  it('counts whole seconds', () => {
    expect(secondsSince('2026-09-24T11:59:30Z', now)).toBe(30)
    expect(secondsSince('2026-09-24T11:59:59.900Z', now)).toBe(0)
  })

  // The server's clock and the phone's can disagree; "-3 s ago" reads as a bug.
  it('never goes negative when the timestamp is in the future', () => {
    expect(secondsSince('2026-09-24T12:00:05Z', now)).toBe(0)
  })

  it('treats an unparseable timestamp as "just now"', () => {
    expect(secondsSince('not a date', now)).toBe(0)
  })
})

describe('formatAgo', () => {
  const t = i18n.getFixedT('en')

  it.each([
    [0, '0 s ago'],
    [59, '59 s ago'],
    [60, '1 min ago'],
    [125, '2 min ago'],
    [3599, '59 min ago'],
    [3600, '1 h ago'],
    [7300, '2 h ago'],
  ])('%d seconds reads "%s"', (seconds, expected) => {
    expect(formatAgo(t, seconds)).toBe(expected)
  })

  it('is translated', () => {
    expect(formatAgo(i18n.getFixedT('ru'), 125)).toBe('2 мин назад')
    expect(formatAgo(i18n.getFixedT('uz'), 30)).toBe('30 soniya oldin')
  })
})
