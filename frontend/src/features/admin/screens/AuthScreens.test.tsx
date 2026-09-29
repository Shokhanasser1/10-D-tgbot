import { act, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
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

  it('offers only the password form when no bot is configured', async () => {
    vi.stubEnv('VITE_TELEGRAM_BOT_USERNAME', '')
    stubAdminBackend(401)
    renderScreen(<AdminApp />, { route: '/admin', path: '/admin/*' })

    expect(await screen.findByLabelText('Login')).toBeInTheDocument()
    expect(screen.getByLabelText('Password')).toBeInTheDocument()
    expect(screen.queryByTestId('telegram-login')).not.toBeInTheDocument()
  })

  it('signs in with a login and password', async () => {
    const user = userEvent.setup()
    stubAdminBackend(401)
    let posted: unknown = null
    server.use(
      http.post(`${API}/internal/auth/password`, async ({ request }) => {
        posted = await request.json()
        return HttpResponse.json(adminMe('dispatcher'))
      }),
      http.get(`${API}/internal/orders`, () => HttpResponse.json({ items: [], total: 0 })),
    )
    renderScreen(<AdminApp />, { route: '/admin', path: '/admin/*' })

    await user.type(await screen.findByLabelText('Login'), ' dilnoza ')
    await user.type(screen.getByLabelText('Password'), 'correct horse battery')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByRole('heading', { name: 'Orders' })).toBeInTheDocument()
    expect(posted).toEqual({ login: 'dilnoza', password: 'correct horse battery' })
  })

  it('says the login or password is wrong without telling which', async () => {
    const user = userEvent.setup()
    stubAdminBackend(401)
    server.use(
      http.post(`${API}/internal/auth/password`, () =>
        HttpResponse.json({ detail: 'Wrong login or password' }, { status: 401 }),
      ),
    )
    renderScreen(<AdminApp />, { route: '/admin', path: '/admin/*' })

    await user.type(await screen.findByLabelText('Login'), 'someone')
    await user.type(screen.getByLabelText('Password'), 'not the password')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Wrong login or password.')
  })
})

describe('ProfileScreen', () => {
  it('forces a new password after an owner reset and then opens the panel', async () => {
    const user = userEvent.setup()
    stubAdminBackend('dispatcher')
    let me = adminMe('dispatcher', { must_change_password: true })
    let posted: unknown = null
    server.use(
      http.get(`${API}/internal/me`, () => HttpResponse.json(me)),
      http.post(`${API}/internal/me/password`, async ({ request }) => {
        posted = await request.json()
        me = adminMe('dispatcher')
        return HttpResponse.json(me)
      }),
      http.get(`${API}/internal/orders`, () => HttpResponse.json({ items: [], total: 0 })),
    )
    renderScreen(<AdminApp />, { route: '/admin', path: '/admin/*' })

    expect(await screen.findByText(/Your password was reset/)).toBeInTheDocument()
    expect(screen.queryByLabelText('Current password')).not.toBeInTheDocument()
    await user.type(screen.getByLabelText('New password'), 'my new password')
    await user.type(screen.getByLabelText('Repeat the new password'), 'my new password')
    await user.click(screen.getByRole('button', { name: 'Save' }))

    expect(await screen.findByRole('heading', { name: 'Orders' })).toBeInTheDocument()
    expect(posted).toEqual({ login: 'dilnoza', new_password: 'my new password' })
  })

  it('asks for the current password to change an existing one, and checks the repeat', async () => {
    const user = userEvent.setup()
    stubAdminBackend('owner')
    renderScreen(<AdminApp />, { route: '/admin/profile', path: '/admin/*' })

    await user.type(await screen.findByLabelText('Current password'), 'old password 1')
    await user.type(screen.getByLabelText('New password'), 'new password 1')
    await user.type(screen.getByLabelText('Repeat the new password'), 'different one')
    await user.click(screen.getByRole('button', { name: 'Save' }))

    expect(screen.getByRole('alert')).toHaveTextContent('The passwords do not match.')
  })
})
