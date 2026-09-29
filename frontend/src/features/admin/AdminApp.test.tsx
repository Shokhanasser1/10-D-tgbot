import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

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
