import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { stubAdminBackend } from '../../../test/mocks/adminBackend'
import { API } from '../../../test/mocks/handlers'
import { server } from '../../../test/mocks/server'
import { renderScreen } from '../../../test/test-utils'
import { AdminsScreen } from './AdminsScreen'

function renderAdmins() {
  return renderScreen(<AdminsScreen currentTelegramId={500} />)
}

describe('AdminsScreen', () => {
  it('lists admins, marking the current one, who cannot deactivate themselves', async () => {
    stubAdminBackend()
    renderAdmins()

    const me = (await screen.findByText('Dilnoza (you)')).closest('li')!
    expect(within(me).getByRole('button', { name: 'Deactivate' })).toBeDisabled()
    const jasur = screen.getByText('Jasur').closest('li')!
    expect(within(jasur).getByRole('combobox', { name: 'Role of Jasur' })).toHaveValue('dispatcher')
  })

  it('adds an admin with a role', async () => {
    const backend = stubAdminBackend()
    renderAdmins()

    await userEvent.type(await screen.findByLabelText('Telegram ID'), '502')
    await userEvent.type(screen.getByLabelText('Name'), 'Nodira')
    await userEvent.selectOptions(screen.getByLabelText('Role'), 'catalog_manager')
    await userEvent.click(screen.getByRole('button', { name: 'Add' }))

    await waitFor(() =>
      expect(backend.writes()[0]).toMatchObject({
        method: 'POST',
        path: '/admins',
        body: { telegram_id: 502, display_name: 'Nodira', role: 'catalog_manager' },
      }),
    )
  })

  it('changes a role straight from the list', async () => {
    const backend = stubAdminBackend()
    renderAdmins()

    await userEvent.selectOptions(
      await screen.findByRole('combobox', { name: 'Role of Jasur' }),
      'owner',
    )

    await waitFor(() =>
      expect(backend.writes()[0]).toMatchObject({
        method: 'PATCH',
        path: '/admins/2',
        body: { role: 'owner' },
      }),
    )
  })

  it('explains why the last owner cannot be demoted', async () => {
    stubAdminBackend()
    server.use(
      http.patch(`${API}/internal/admins/:id`, () =>
        HttpResponse.json({ detail: 'x', code: 'last_owner' }, { status: 409 }),
      ),
    )
    renderAdmins()

    await userEvent.selectOptions(
      await screen.findByRole('combobox', { name: 'Role of Dilnoza' }),
      'dispatcher',
    )

    expect(await screen.findByRole('alert')).toHaveTextContent('at least one active owner')
  })
})
