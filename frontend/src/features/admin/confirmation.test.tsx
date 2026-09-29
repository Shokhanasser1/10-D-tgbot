import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { adminMe, adminOrder } from '../../test/adminFixtures'
import { stubAdminBackend } from '../../test/mocks/adminBackend'
import { API } from '../../test/mocks/handlers'
import { server } from '../../test/mocks/server'
import { renderScreen } from '../../test/test-utils'
import { AdminApp } from './AdminApp'

const confirmNeeded = () =>
  HttpResponse.json(
    { detail: 'Confirm with your password', code: 'password_confirmation_required' },
    { status: 403 },
  )

describe('password confirmation', () => {
  it('asks for the password, confirms, and retries the refund once', async () => {
    const user = userEvent.setup()
    stubAdminBackend('accountant')
    const order = adminOrder({
      status: 'cancelled',
      can_cancel: false,
      payment: { status: 'succeeded', amount: '34.97', refund_status: 'failed' },
    })
    let confirmedWith: unknown = null
    let refundCalls = 0
    server.use(
      http.get(`${API}/internal/orders/:id`, () => HttpResponse.json(order)),
      http.post(`${API}/internal/auth/confirm`, async ({ request }) => {
        confirmedWith = {
          body: await request.json(),
          csrf: request.headers.get('x-requested-with'),
        }
        return new HttpResponse(null, { status: 204 })
      }),
      http.post(`${API}/internal/orders/:id/refund`, () => {
        refundCalls += 1
        return refundCalls === 1 ? confirmNeeded() : HttpResponse.json(order)
      }),
    )
    renderScreen(<AdminApp />, { route: '/admin/orders/42', path: '/admin/*' })

    await user.click(await screen.findByRole('button', { name: 'Retry refund' }))
    await user.type(await screen.findByLabelText('Password'), 'correct horse battery')
    await user.click(screen.getByRole('button', { name: 'Confirm' }))

    await waitFor(() => expect(refundCalls).toBe(2))
    expect(confirmedWith).toEqual({
      body: { password: 'correct horse battery' },
      csrf: 'admin',
    })
  })

  it('sends an admin without a password to the profile', async () => {
    const user = userEvent.setup()
    stubAdminBackend('accountant')
    server.use(
      http.get(`${API}/internal/me`, () =>
        HttpResponse.json(adminMe('accountant', { has_password: false, login: null })),
      ),
      http.get(`${API}/internal/orders/:id`, () =>
        HttpResponse.json(
          adminOrder({
            status: 'cancelled',
            can_cancel: false,
            payment: { status: 'succeeded', amount: '34.97', refund_status: 'failed' },
          }),
        ),
      ),
      http.post(`${API}/internal/orders/:id/refund`, () => confirmNeeded()),
    )
    renderScreen(<AdminApp />, { route: '/admin/orders/42', path: '/admin/*' })

    await user.click(await screen.findByRole('button', { name: 'Retry refund' }))

    expect(await screen.findByRole('heading', { name: 'Profile' })).toBeInTheDocument()
  })
})

describe('permissions in the panel', () => {
  it('shows a viewer the catalog read-only', async () => {
    stubAdminBackend('viewer')
    renderScreen(<AdminApp />, { route: '/admin/catalog', path: '/admin/*' })

    expect(await screen.findByRole('heading', { name: 'Catalog' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /New product/ })).not.toBeInTheDocument()
  })

  it('hides cancelling a paid order from a dispatcher', async () => {
    stubAdminBackend('dispatcher')
    renderScreen(<AdminApp />, { route: '/admin/orders/42', path: '/admin/*' })

    expect(await screen.findByRole('heading', { name: 'Order #42' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Cancel and refund' })).not.toBeInTheDocument()
  })

  it('lets an owner reset another admin and shows the temporary password once', async () => {
    const user = userEvent.setup()
    stubAdminBackend('owner')
    server.use(
      http.post(`${API}/internal/admins/:id/password-reset`, () =>
        HttpResponse.json({ login: 'bekzod', temporary_password: 'Tmp-12345abc' }),
      ),
    )
    renderScreen(<AdminApp />, { route: '/admin/admins', path: '/admin/*' })

    const buttons = await screen.findAllByRole('button', { name: 'Reset password' })
    await user.click(buttons[0])

    expect(await screen.findByText('Tmp-12345abc')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Done' }))
    expect(screen.queryByText('Tmp-12345abc')).not.toBeInTheDocument()
  })
})
