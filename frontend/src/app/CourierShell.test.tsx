import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { adminMe } from '../test/adminFixtures'
import { API } from '../test/mocks/handlers'
import { server } from '../test/mocks/server'
import { renderScreen } from '../test/test-utils'
import { CourierShell } from './CourierShell'

const options = {
  route: '/courier',
  path: '/courier',
  extraRoutes: [
    { path: '/', element: <div>shop home</div> },
    { path: '/admin', element: <div>admin page</div> },
  ],
}

describe('CourierShell', () => {
  it('takes a courier to the shop', async () => {
    const user = userEvent.setup()
    renderScreen(<CourierShell />, options)

    await user.click(screen.getByRole('button', { name: 'Shop' }))

    expect(await screen.findByText('shop home')).toBeInTheDocument()
  })

  it('has no cart and no orders button', () => {
    renderScreen(<CourierShell />, options)

    expect(screen.queryByRole('button', { name: 'Cart' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'My orders' })).not.toBeInTheDocument()
  })

  it('hides the admin button from a courier who is not an admin', async () => {
    renderScreen(<CourierShell />, options)

    // Let the admin check settle before asserting that nothing appeared.
    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(screen.queryByRole('button', { name: 'Admin panel' })).not.toBeInTheDocument()
  })

  it('takes a courier who is also an admin to the panel', async () => {
    const user = userEvent.setup()
    server.use(http.get(`${API}/internal/me`, () => HttpResponse.json(adminMe('dispatcher'))))
    renderScreen(<CourierShell />, options)

    await user.click(await screen.findByRole('button', { name: 'Admin panel' }))

    expect(await screen.findByText('admin page')).toBeInTheDocument()
  })
})
