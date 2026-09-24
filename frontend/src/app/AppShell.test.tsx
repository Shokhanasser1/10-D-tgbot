import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { stubCourierBackend } from '../test/mocks/courierBackend'
import { API } from '../test/mocks/handlers'
import { server } from '../test/mocks/server'
import { renderScreen } from '../test/test-utils'
import { AppShell } from './AppShell'

const options = {
  extraRoutes: [
    { path: '/courier', element: <div>courier page</div> },
    { path: '/orders', element: <div>orders page</div> },
  ],
}

describe('AppShell courier entry', () => {
  it('is hidden from a customer, for whom the courier endpoint answers 403', async () => {
    renderScreen(<AppShell />, options)

    await screen.findByRole('button', { name: 'My orders' })
    // Let the profile request settle before asserting that nothing appeared.
    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(screen.queryByRole('button', { name: 'Courier' })).not.toBeInTheDocument()
  })

  it.each([401, 500])('is hidden when the profile request fails with %d', async (status) => {
    server.use(http.get(`${API}/courier/me`, () => new HttpResponse(null, { status })))
    renderScreen(<AppShell />, options)

    await screen.findByRole('button', { name: 'My orders' })
    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(screen.queryByRole('button', { name: 'Courier' })).not.toBeInTheDocument()
  })

  it('is shown to a courier and opens the courier section', async () => {
    const user = userEvent.setup()
    stubCourierBackend()
    renderScreen(<AppShell />, options)

    await user.click(await screen.findByRole('button', { name: 'Courier' }))

    expect(await screen.findByText('courier page')).toBeInTheDocument()
  })

  it('still lets a courier reach their own orders', async () => {
    const user = userEvent.setup()
    stubCourierBackend()
    renderScreen(<AppShell />, options)
    await screen.findByRole('button', { name: 'Courier' })

    await user.click(screen.getByRole('button', { name: 'My orders' }))

    expect(await screen.findByText('orders page')).toBeInTheDocument()
  })
})
