import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { stubAdminBackend } from '../../../test/mocks/adminBackend'
import { renderScreen } from '../../../test/test-utils'
import { adminMe } from '../../../test/adminFixtures'
import { AdminMeProvider } from '../meContext'
import { CategoriesScreen } from './CategoriesScreen'

describe('CategoriesScreen', () => {
  it('lists categories and attributes with their slugs and keys', async () => {
    stubAdminBackend()
    renderScreen(<CategoriesScreen />)

    expect(await screen.findByText('lipstick')).toBeInTheDocument()
    expect(screen.getByText('serums')).toBeInTheDocument()
    expect(screen.getByText('shade · Lipstick')).toBeInTheDocument()
  })

  it('adds a category', async () => {
    const backend = stubAdminBackend()
    renderScreen(<CategoriesScreen />)

    const heading = await screen.findByRole('heading', { name: 'Add category' })
    const form = heading.nextElementSibling as HTMLElement
    await userEvent.type(within(form).getByLabelText('Slug'), 'lip-care')
    await userEvent.clear(within(form).getByLabelText('Sort order'))
    await userEvent.type(within(form).getByLabelText('Sort order'), '3')
    await userEvent.click(within(form).getByRole('button', { name: 'Add category' }))

    await waitFor(() =>
      expect(backend.writes()[0]).toMatchObject({
        method: 'POST',
        path: '/categories',
        body: { slug: 'lip-care', sort_order: 3 },
      }),
    )
  })

  it('adds an attribute to a category', async () => {
    const backend = stubAdminBackend()
    renderScreen(<CategoriesScreen />)

    const heading = await screen.findByRole('heading', { name: 'Add attribute' })
    const form = heading.nextElementSibling as HTMLElement
    await userEvent.type(within(form).getByLabelText('Key'), 'volume_ml')
    await userEvent.selectOptions(within(form).getByLabelText('Category'), '2')
    await userEvent.selectOptions(within(form).getByLabelText('Value type'), 'number')
    await userEvent.click(within(form).getByRole('button', { name: 'Add attribute' }))

    await waitFor(() =>
      expect(backend.writes()[0]).toMatchObject({
        method: 'POST',
        path: '/attributes',
        body: { key: 'volume_ml', category_id: 2, value_type: 'number' },
      }),
    )
  })

  it('translates a category name', async () => {
    const backend = stubAdminBackend()
    renderScreen(<CategoriesScreen />)

    const item = (await screen.findByText('serums')).closest('details')!
    await userEvent.click(within(item).getByText('Serums'))
    await userEvent.click(within(item).getByRole('tab', { name: /^RU/ }))
    await userEvent.type(within(item).getByLabelText('Name (RU)'), 'Сыворотки')
    const translations = within(item).getByLabelText('Name (RU)').closest('form')!
    await userEvent.click(within(translations).getByRole('button', { name: 'Save' }))

    await waitFor(() =>
      expect(backend.writes()[0].body).toEqual({
        entity_type: 'category',
        entity_id: 2,
        locale: 'ru',
        field: 'name',
        value: 'Сыворотки',
      }),
    )
  })
})

describe('CategoriesScreen: a seller (Spec 9)', () => {
  it('is read-only without taxonomy.edit, even with catalog.edit', async () => {
    stubAdminBackend('seller')
    renderScreen(
      <AdminMeProvider value={adminMe('seller')}>
        <CategoriesScreen />
      </AdminMeProvider>,
    )

    expect(await screen.findByText('View only: your role cannot change this.')).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'Add category' })[0]).toBeDisabled()
  })
})
