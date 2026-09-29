import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  getInitDataRaw,
  isTelegramEnv,
  openExternalLink,
  openTelegramLink,
  requestWriteAccessIfNeeded,
} from './webApp'

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

describe('opening links', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it.each([
    ['openExternalLink', openExternalLink, 'openLink'],
    ['openTelegramLink', openTelegramLink, 'openTelegramLink'],
  ] as const)('%s hands the URL to Telegram when it is available', (_name, open, method) => {
    const handler = vi.fn()
    const windowOpen = vi.spyOn(window, 'open').mockReturnValue(null)
    window.Telegram = {
      WebApp: { initData: 'x', [method]: handler },
    } as unknown as Window['Telegram']

    open('https://t.me/some_bot')

    expect(handler).toHaveBeenCalledWith('https://t.me/some_bot')
    expect(windowOpen).not.toHaveBeenCalled()
  })

  it.each([
    ['openExternalLink', openExternalLink],
    ['openTelegramLink', openTelegramLink],
  ] as const)('%s opens a new tab without an opener outside Telegram', (_name, open) => {
    const windowOpen = vi.spyOn(window, 'open').mockReturnValue(null)

    open('https://example.com/page')

    expect(windowOpen).toHaveBeenCalledWith('https://example.com/page', '_blank', 'noopener')
  })

  it.each(['javascript:alert(1)', 'data:text/html,hi', 'tg://resolve?domain=x', '/relative', ''])(
    'refuses to open %j',
    (url) => {
      const handler = vi.fn()
      const windowOpen = vi.spyOn(window, 'open').mockReturnValue(null)
      window.Telegram = {
        WebApp: { initData: 'x', openLink: handler, openTelegramLink: handler },
      } as unknown as Window['Telegram']

      openExternalLink(url)
      openTelegramLink(url)

      expect(handler).not.toHaveBeenCalled()
      expect(windowOpen).not.toHaveBeenCalled()
    },
  )
})

describe('requestWriteAccessIfNeeded', () => {
  function stubUser(allows: boolean | undefined, initData = 'query_id=abc&hash=def') {
    const requestWriteAccess = vi.fn()
    window.Telegram = {
      WebApp: {
        initData,
        initDataUnsafe: { user: { id: 1, allows_write_to_pm: allows } },
        isVersionAtLeast: () => true,
        requestWriteAccess,
      },
    } as unknown as Window['Telegram']
    return requestWriteAccess
  }

  it('asks when the bot may not write to the user yet', () => {
    const request = stubUser(false)
    requestWriteAccessIfNeeded()
    expect(request).toHaveBeenCalledTimes(1)
  })

  it('does not ask when writing is already allowed or unknown', () => {
    const allowed = stubUser(true)
    requestWriteAccessIfNeeded()
    expect(allowed).not.toHaveBeenCalled()

    const unknown = stubUser(undefined)
    requestWriteAccessIfNeeded()
    expect(unknown).not.toHaveBeenCalled()
  })

  it('does nothing outside Telegram', () => {
    const request = stubUser(false, '')
    requestWriteAccessIfNeeded()
    expect(request).not.toHaveBeenCalled()
  })
})
