import { afterEach, describe, expect, it } from 'vitest'

import { getInitDataRaw, isTelegramEnv } from './webApp'

function stubTelegram(initData: string) {
  window.Telegram = { WebApp: { initData } } as unknown as Window['Telegram']
}

afterEach(() => {
  delete window.Telegram
})

describe('isTelegramEnv', () => {
  it('is false when the Telegram script never loaded', () => {
    expect(isTelegramEnv()).toBe(false)
  })

  // Regression: Telegram's script defines window.Telegram.WebApp even when loaded outside a
  // real client, with empty initData. Object presence alone wrongly reported "in Telegram".
  it('is false for the standalone stub that has empty initData', () => {
    stubTelegram('')

    expect(isTelegramEnv()).toBe(false)
  })

  it('is true when Telegram supplies real launch data', () => {
    stubTelegram('query_id=abc&hash=def')

    expect(isTelegramEnv()).toBe(true)
  })
})

describe('getInitDataRaw', () => {
  it('prefers the real Telegram initData', () => {
    stubTelegram('real-init-data')

    expect(getInitDataRaw()).toBe('real-init-data')
  })

  it('falls back to the dev mock outside Telegram', () => {
    stubTelegram('')

    expect(getInitDataRaw()).toBe('mock-init-data')
  })
})
