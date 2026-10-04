import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { stubAdminBackend } from '../../../test/mocks/adminBackend'
import { API } from '../../../test/mocks/handlers'
import { server } from '../../../test/mocks/server'
import { renderScreen } from '../../../test/test-utils'
import { adminMe } from '../../../test/adminFixtures'
import { AdminMeProvider } from '../meContext'
import { ProductEditorScreen } from './ProductEditorScreen'

function renderEditor() {
  return renderScreen(<ProductEditorScreen productId={1} />)
}

describe('ProductEditorScreen: new product', () => {
  it('creates the product and continues in its editor', async () => {
    const backend = stubAdminBackend()
    renderScreen(<ProductEditorScreen productId={null} />, {
      route: '/admin/catalog/new',
      path: '/admin/catalog/new',
      extraRoutes: [{ path: '/admin/catalog/products/:id', element: <p>editor opened</p> }],
    })

    await userEvent.selectOptions(await screen.findByLabelText('Category'), '2')
    await userEvent.selectOptions(await screen.findByLabelText('Seller'), '7')
    await userEvent.type(screen.getByLabelText('SKU'), ' SERUM-NEW ')
    await userEvent.type(screen.getByLabelText('Base price'), '12.5')
    await userEvent.click(screen.getByRole('button', { name: 'Create and continue' }))

    expect(await screen.findByText('editor opened')).toBeInTheDocument()
    expect(backend.writes()[0]).toMatchObject({
      method: 'POST',
      path: '/products',
      body: {
        category_id: 2,
        seller_id: 7,
        base_sku: 'SERUM-NEW',
        base_price: '12.5',
        status: 'draft',
      },
    })
  })

  it('refuses a malformed price before calling the API', async () => {
    const backend = stubAdminBackend()
    renderScreen(<ProductEditorScreen productId={null} />)

    await userEvent.selectOptions(await screen.findByLabelText('Category'), '1')
    await userEvent.selectOptions(await screen.findByLabelText('Seller'), '7')
    await userEvent.type(screen.getByLabelText('SKU'), 'X')
    await userEvent.type(screen.getByLabelText('Base price'), '12,50')
    await userEvent.click(screen.getByRole('button', { name: 'Create and continue' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Enter a price like 19.99.')
    expect(backend.writes()).toEqual([])
  })

  it('explains a duplicate SKU', async () => {
    stubAdminBackend()
    server.use(
      http.post(`${API}/internal/products`, () =>
        HttpResponse.json({ detail: 'Request conflicts with existing data' }, { status: 400 }),
      ),
    )
    renderScreen(<ProductEditorScreen productId={null} />)

    await userEvent.selectOptions(await screen.findByLabelText('Category'), '1')
    await userEvent.selectOptions(await screen.findByLabelText('Seller'), '7')
    await userEvent.type(screen.getByLabelText('SKU'), 'LIP-VELVET')
    await userEvent.type(screen.getByLabelText('Base price'), '1')
    await userEvent.click(screen.getByRole('button', { name: 'Create and continue' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('SKU or slug may already be in use')
  })
})

describe('ProductEditorScreen: existing product', () => {
  it('saves the basics', async () => {
    const backend = stubAdminBackend()
    renderEditor()

    const status = await screen.findByLabelText('Status')
    await userEvent.selectOptions(status, 'archived')
    const basics = status.closest('form')!
    await userEvent.click(within(basics).getByRole('button', { name: 'Save' }))

    await waitFor(() =>
      expect(backend.writes()[0]).toMatchObject({
        method: 'PATCH',
        path: '/products/1',
        body: { status: 'archived', base_sku: 'LIP-VELVET', category_id: 1 },
      }),
    )
  })

  it('sends only the translations that changed, per language', async () => {
    const backend = stubAdminBackend()
    renderEditor()

    await userEvent.click(await screen.findByRole('tab', { name: /^UZ/ }))
    await userEvent.type(screen.getByLabelText('Name (UZ)'), 'Baxmal pomada')
    await userEvent.click(screen.getByRole('tab', { name: /^EN/ }))
    const name = screen.getByLabelText('Name (EN)')
    expect(name).toHaveValue('Velvet Matte Lipstick')
    const form = name.closest('form')!
    await userEvent.click(within(form).getByRole('button', { name: 'Save' }))

    await waitFor(() => expect(within(form).getByText('Saved')).toBeInTheDocument())
    expect(backend.writes().map((w) => w.body)).toEqual([
      { entity_type: 'product', entity_id: 1, locale: 'uz', field: 'name', value: 'Baxmal pomada' },
    ])
  })

  it('marks languages with missing texts', async () => {
    stubAdminBackend()
    renderEditor()

    expect(await screen.findByRole('tab', { name: 'EN' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'RU •' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'UZ •' })).toBeInTheDocument()
  })

  it('edits a variant including its attribute values', async () => {
    const backend = stubAdminBackend()
    renderEditor()

    const row = await screen.findByRole('form', { name: 'LIP-VELVET-RED' })
    const stock = within(row).getByLabelText('Stock')
    await userEvent.clear(stock)
    await userEvent.type(stock, '12')
    const shade = within(row).getByLabelText('Shade')
    await userEvent.clear(shade)
    await userEvent.type(shade, 'Ruby')
    await userEvent.click(within(row).getByRole('button', { name: 'Save' }))

    await waitFor(() =>
      expect(backend.writes()[0]).toMatchObject({
        method: 'PATCH',
        path: '/variants/11',
        body: { stock_qty: 12, attribute_values: { shade: 'Ruby' }, price: '19.99' },
      }),
    )
  })

  it('adds a variant priced at the base price by default', async () => {
    const backend = stubAdminBackend()
    renderEditor()

    const row = await screen.findByRole('form', { name: 'New variant' })
    await userEvent.type(within(row).getByLabelText('SKU'), 'LIP-VELVET-NUDE')
    await userEvent.click(within(row).getByRole('button', { name: 'Add' }))

    await waitFor(() =>
      expect(backend.writes()[0]).toMatchObject({
        method: 'POST',
        path: '/variants',
        body: { product_id: 1, sku: 'LIP-VELVET-NUDE', price: '19.99', stock_qty: 0 },
      }),
    )
  })

  it('shows photos in their order and uploads new ones after them', async () => {
    const backend = stubAdminBackend()
    renderEditor()

    await screen.findAllByRole('button', { name: 'Move earlier' })
    const images = document.querySelectorAll('img')
    expect([...images].map((img) => img.getAttribute('src'))).toEqual([
      '/media/products/a.webp',
      '/media/products/b.webp',
    ])

    const input = document.querySelector('input[type=file]') as HTMLInputElement
    await userEvent.upload(input, new File(['x'], 'new.jpg', { type: 'image/jpeg' }))

    await waitFor(() =>
      expect(backend.writes()[0]).toMatchObject({
        method: 'POST',
        path: '/products/1/images',
        body: 'multipart',
      }),
    )
  })

  it('reorders photos by renumbering their positions', async () => {
    const backend = stubAdminBackend()
    renderEditor()

    const later = await screen.findAllByRole('button', { name: 'Move later' })
    await userEvent.click(later[0])

    await waitFor(() => expect(backend.writes()).toHaveLength(2))
    expect(
      backend
        .writes()
        .map((w) => [w.path, w.body])
        .sort(),
    ).toEqual([
      ['/images/30', { position: 1 }],
      ['/images/31', { position: 0 }],
    ])
  })

  it('deletes a photo only after confirming', async () => {
    const backend = stubAdminBackend()
    renderEditor()

    const [first] = await screen.findAllByRole('button', { name: 'Delete photo' })
    await userEvent.click(first)
    expect(backend.writes()).toEqual([])
    await userEvent.click(await screen.findByRole('button', { name: 'Delete' }))

    await waitFor(() =>
      expect(backend.writes()[0]).toMatchObject({ method: 'DELETE', path: '/images/30' }),
    )
  })
})

describe('ProductEditorScreen: a seller (Spec 9)', () => {
  it("creates the product for the seller's own shop without asking whose it is", async () => {
    const backend = stubAdminBackend('seller')
    renderScreen(
      <AdminMeProvider value={adminMe('seller')}>
        <ProductEditorScreen productId={null} />
      </AdminMeProvider>,
      {
        route: '/admin/catalog/new',
        path: '/admin/catalog/new',
        extraRoutes: [{ path: '/admin/catalog/products/:id', element: <p>editor opened</p> }],
      },
    )

    await userEvent.selectOptions(await screen.findByLabelText('Category'), '2')
    expect(screen.queryByLabelText('Seller')).not.toBeInTheDocument()
    await userEvent.type(screen.getByLabelText('SKU'), 'LOLA-NEW')
    await userEvent.type(screen.getByLabelText('Base price'), '9')
    await userEvent.click(screen.getByRole('button', { name: 'Create and continue' }))

    expect(await screen.findByText('editor opened')).toBeInTheDocument()
    expect(backend.writes()[0].body).not.toHaveProperty('seller_id')
  })
})
