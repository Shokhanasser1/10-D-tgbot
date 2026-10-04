import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { delay, http, HttpResponse } from 'msw'
import { useNavigate } from 'react-router-dom'
import { beforeEach, describe, expect, it } from 'vitest'

import { adminMe } from '../test/adminFixtures'
import { courierProfile } from '../test/fixtures'
import { API } from '../test/mocks/handlers'
import { server } from '../test/mocks/server'
import { renderScreen } from '../test/test-utils'
import { startLaunch } from './launch'
import { LaunchGate } from './LaunchGate'

function BackToShop() {
  const navigate = useNavigate()
  return (
    <button type="button" onClick={() => navigate('/')}>
      to shop
    </button>
  )
}

function renderLaunch(timeoutMs?: number) {
  return renderScreen(
    <LaunchGate timeoutMs={timeoutMs}>
      <div>shop home</div>
    </LaunchGate>,
    {
      extraRoutes: [
        { path: '/admin', element: <div>admin page</div> },
        {
          path: '/courier',
          element: (
            <div>
              courier page <BackToShop />
            </div>
          ),
        },
      ],
    },
  )
}

function asAdmin() {
  server.use(http.get(`${API}/internal/me`, () => HttpResponse.json(adminMe('dispatcher'))))
}

function asCourier() {
  server.use(http.get(`${API}/courier/me`, () => HttpResponse.json(courierProfile)))
}

function failing(path: string) {
  server.use(http.get(`${API}${path}`, () => new HttpResponse(null, { status: 500 })))
}

const settle = () => new Promise((resolve) => setTimeout(resolve, 50))

beforeEach(() => startLaunch('/'))

describe('LaunchGate: opened at the root', () => {
  it('shows a customer the shop', async () => {
    renderLaunch()

    expect(await screen.findByText('shop home')).toBeInTheDocument()
  })

  it('sends a courier to the courier screen', async () => {
    asCourier()
    renderLaunch()

    expect(await screen.findByText('courier page')).toBeInTheDocument()
  })

  it('sends an admin to the admin panel', async () => {
    asAdmin()
    renderLaunch()

    expect(await screen.findByText('admin page')).toBeInTheDocument()
  })

  it('prefers the admin panel for someone who is both', async () => {
    asAdmin()
    asCourier()
    renderLaunch()

    expect(await screen.findByText('admin page')).toBeInTheDocument()
  })

  it('still sends a courier on when the admin check fails', async () => {
    failing('/internal/me')
    asCourier()
    renderLaunch()

    expect(await screen.findByText('courier page')).toBeInTheDocument()
  })

  it('shows the shop when both checks fail', async () => {
    failing('/internal/me')
    failing('/courier/me')
    renderLaunch()

    expect(await screen.findByText('shop home')).toBeInTheDocument()
  })

  it('shows a loading skeleton, not the shop, while checking', async () => {
    server.use(
      http.get(`${API}/internal/me`, async () => {
        await delay(100)
        return HttpResponse.json({ detail: 'Not an admin' }, { status: 403 })
      }),
    )
    renderLaunch()

    expect(screen.getByRole('status', { name: 'Loading…' })).toBeInTheDocument()
    expect(screen.queryByText('shop home')).not.toBeInTheDocument()
    expect(await screen.findByText('shop home')).toBeInTheDocument()
  })

  it('shows the shop after the timeout and ignores a late answer', async () => {
    server.use(
      http.get(`${API}/internal/me`, async () => {
        await delay(300)
        return HttpResponse.json(adminMe('owner'))
      }),
    )
    renderLaunch(50)

    expect(await screen.findByText('shop home')).toBeInTheDocument()
    await new Promise((resolve) => setTimeout(resolve, 400))
    expect(screen.getByText('shop home')).toBeInTheDocument()
    expect(screen.queryByText('admin page')).not.toBeInTheDocument()
  })

  it('lets a courier go back to the shop without bouncing', async () => {
    const user = userEvent.setup()
    asCourier()
    renderLaunch()

    await user.click(await screen.findByRole('button', { name: 'to shop' }))

    expect(await screen.findByText('shop home')).toBeInTheDocument()
    await settle()
    expect(screen.queryByText('courier page')).not.toBeInTheDocument()
  })
})

describe('LaunchGate: opened anywhere else', () => {
  it('never redirects, even for a courier', async () => {
    startLaunch('/orders/1')
    asCourier()
    renderLaunch()

    expect(screen.getByText('shop home')).toBeInTheDocument()
    await settle()
    expect(screen.queryByText('courier page')).not.toBeInTheDocument()
  })
})
