import { act, screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { adminMe } from '../../../test/adminFixtures'
import { stubAdminBackend } from '../../../test/mocks/adminBackend'
import { API } from '../../../test/mocks/handlers'
import { server } from '../../../test/mocks/server'
import { renderScreen } from '../../../test/test-utils'
import { AdminApp } from '../AdminApp'
import type { TelegramLoginData } from '../types'

const WIDGET_USER: TelegramLoginData = { id: 500, auth_date: 1_700_000_000, hash: 'abc' }

function signInWithWidget() {
  const callback = (window as unknown as Record<string, (u: TelegramLoginData) => void>)
    .__onAdminTelegramAuth
  act(() => callback(WIDGET_USER))
}

afterEach(() => vi.unstubAllEnvs())

describe('LoginScreen', () => {
  it('embeds the Telegram widget for the configured bot', async () => {
    vi.stubEnv('VITE_TELEGRAM_BOT_USERNAME', '@shop_bot')
    stubAdminBackend(401)
    renderScreen(<AdminApp />, { route: '/admin', path: '/admin/*' })

    const host = await screen.findByTestId('telegram-login')
    const script = host.querySelector('script')
    expect(script?.getAttribute('src')).toContain('telegram.org/js/telegram-widget.js')
    expect(script?.getAttribute('data-telegram-login')).toBe('shop_bot')
  })

  it('exchanges the widget payload for a session and opens the panel', async () => {
    vi.stubEnv('VITE_TELEGRAM_BOT_USERNAME', 'shop_bot')
    stubAdminBackend(401)
    let posted: unknown = null
    server.use(
      http.post(`${API}/internal/auth/telegram`, async ({ request }) => {
        posted = await request.json()
        return HttpResponse.json(adminMe('dispatcher'))
      }),
      // After sign-in the orders screen loads; its data is not what this test is about.
      http.get(`${API}/internal/orders`, () => HttpResponse.json({ items: [], total: 0 })),
    )
    renderScreen(<AdminApp />, { route: '/admin', path: '/admin/*' })
    await screen.findByTestId('telegram-login')

    signInWithWidget()

    expect(await screen.findByRole('heading', { name: 'Orders' })).toBeInTheDocument()
    expect(posted).toEqual(WIDGET_USER)
  })

  it('says so when the Telegram account is not an admin', async () => {
    vi.stubEnv('VITE_TELEGRAM_BOT_USERNAME', 'shop_bot')
    stubAdminBackend(401)
    server.use(
      http.post(`${API}/internal/auth/telegram`, () =>
        HttpResponse.json({ detail: 'Not an admin' }, { status: 403 }),
      ),
    )
    renderScreen(<AdminApp />, { route: '/admin', path: '/admin/*' })
    await screen.findByTestId('telegram-login')

    signInWithWidget()

    expect(await screen.findByRole('alert')).toHaveTextContent('not an admin')
  })

  it('explains a missing bot username instead of showing a broken widget', async () => {
    vi.stubEnv('VITE_TELEGRAM_BOT_USERNAME', '')
    stubAdminBackend(401)
    renderScreen(<AdminApp />, { route: '/admin', path: '/admin/*' })

    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent('Browser sign-in is not set up'),
    )
    expect(screen.queryByTestId('telegram-login')).not.toBeInTheDocument()
  })
})
