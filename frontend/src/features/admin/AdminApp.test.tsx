import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { courierProfile } from '../../test/fixtures'
import { API } from '../../test/mocks/handlers'
import { stubAdminBackend } from '../../test/mocks/adminBackend'
import { server } from '../../test/mocks/server'
import { renderScreen } from '../../test/test-utils'
import { AdminApp } from './AdminApp'

export function renderAdmin(route = '/admin') {
  return renderScreen(<AdminApp />, { route, path: '/admin/*' })
}

async function navLinks(): Promise<string[]> {
  const nav = await screen.findByRole('navigation')
  return within(nav)
    .getAllByRole('link')
    .map((link) => link.textContent ?? '')
}

describe('AdminApp', () => {
  it('shows the sign-in screen when nobody is signed in', async () => {
    stubAdminBackend(401)
    renderAdmin()

    expect(await screen.findByRole('heading', { name: 'Admin sign-in' })).toBeInTheDocument()
  })

  it('shows "no access" to a Telegram user who is not an admin', async () => {
    stubAdminBackend(403)
    renderAdmin()

    expect(await screen.findByRole('heading', { name: 'No access' })).toBeInTheDocument()
  })

  it('gives an owner every section and lands on the summary', async () => {
    stubAdminBackend('owner')
    renderAdmin()

    expect(await navLinks()).toEqual([
      'Summary',
      'Catalog',
      'Orders',
      'Couriers',
      'Sellers',
      'Admins',
      'Profile',
    ])
    expect(await screen.findByRole('heading', { name: 'Summary' })).toBeInTheDocument()
    expect(screen.getByText('Dilnoza')).toBeInTheDocument()
    expect(screen.getByText('Owner')).toBeInTheDocument()
  })

  it('gives a catalog manager only the catalog', async () => {
    stubAdminBackend('catalog_manager')
    renderAdmin()

    expect(await navLinks()).toEqual(['Catalog', 'Profile'])
    expect(await screen.findByRole('heading', { name: 'Catalog' })).toBeInTheDocument()
  })

  it('gives a dispatcher orders and couriers, landing on orders', async () => {
    stubAdminBackend('dispatcher')
    renderAdmin()

    expect(await navLinks()).toEqual(['Orders', 'Couriers', 'Profile'])
    expect(await screen.findByRole('heading', { name: 'Orders' })).toBeInTheDocument()
  })

  it('sends a role away from a section it may not open', async () => {
    stubAdminBackend('dispatcher')
    renderAdmin('/admin/summary')

    expect(await screen.findByRole('heading', { name: 'Orders' })).toBeInTheDocument()
    expect(screen.queryByText('Revenue')).not.toBeInTheDocument()
  })

  it('returns to the sign-in screen when the session ends mid-use', async () => {
    const backend = stubAdminBackend('owner')
    renderAdmin('/admin/summary')
    await screen.findByText('Revenue')
    expect(backend.requests.length).toBeGreaterThan(0)

    server.use(
      http.get(`${API}/internal/me`, () => HttpResponse.json({}, { status: 401 })),
      http.get(`${API}/internal/stats/summary`, () => HttpResponse.json({}, { status: 401 })),
    )
    await userEvent.click(screen.getByRole('tab', { name: '7 days' }))

    expect(await screen.findByRole('heading', { name: 'Admin sign-in' })).toBeInTheDocument()
  })

  it('switches the interface language', async () => {
    stubAdminBackend('owner')
    renderAdmin()
    await navLinks()

    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Language' }), 'ru')

    await waitFor(async () => expect(await navLinks()).toContain('Сводка'))
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Язык' }), 'en')
  })
})

describe('AdminApp: switching to other screens', () => {
  const withOtherScreens = {
    route: '/admin',
    path: '/admin/*',
    extraRoutes: [
      { path: '/', element: <div>shop home</div> },
      { path: '/courier', element: <div>courier page</div> },
    ],
  }

  it('takes an admin to the shop', async () => {
    const user = userEvent.setup()
    stubAdminBackend('owner')
    renderScreen(<AdminApp />, withOtherScreens)

    await user.click(await screen.findByRole('button', { name: 'Shop' }))

    expect(await screen.findByText('shop home')).toBeInTheDocument()
  })

  it('hides the courier button from an admin who is not a courier', async () => {
    stubAdminBackend('owner')
    renderScreen(<AdminApp />, withOtherScreens)

    await screen.findByRole('button', { name: 'Shop' })
    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(screen.queryByRole('button', { name: 'Courier' })).not.toBeInTheDocument()
  })

  it('takes an admin who is also a courier to the courier screen', async () => {
    const user = userEvent.setup()
    stubAdminBackend('owner')
    server.use(http.get(`${API}/courier/me`, () => HttpResponse.json(courierProfile)))
    renderScreen(<AdminApp />, withOtherScreens)

    await user.click(await screen.findByRole('button', { name: 'Courier' }))

    expect(await screen.findByText('courier page')).toBeInTheDocument()
  })
})

describe('AdminApp: a seller (Spec 9)', () => {
  it('gives a seller only the catalog and names the shop in the header', async () => {
    stubAdminBackend('seller')
    renderAdmin()

    expect(await navLinks()).toEqual(['Catalog', 'Orders', 'Money', 'Profile'])
    expect(await screen.findByRole('heading', { name: 'Catalog' })).toBeInTheDocument()
    expect(screen.getByText('Lola Beauty')).toBeInTheDocument()
  })

  it('opens the sellers section for an owner', async () => {
    stubAdminBackend('owner')
    renderAdmin('/admin/sellers')

    expect(await screen.findByRole('heading', { name: 'Sellers' })).toBeInTheDocument()
  })
})

describe("AdminApp: a seller's orders (Spec 10)", () => {
  it("opens the seller's own orders, not the platform's", async () => {
    stubAdminBackend('seller')
    renderAdmin('/admin/orders/42')

    expect(await screen.findByRole('button', { name: 'Ready for pickup' })).toBeInTheDocument()
    expect(screen.queryByText('Aziza K')).not.toBeInTheDocument()
  })
})
