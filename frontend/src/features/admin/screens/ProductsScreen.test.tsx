import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { adminProductList } from '../../../test/adminFixtures'
import { stubAdminBackend } from '../../../test/mocks/adminBackend'
import { API } from '../../../test/mocks/handlers'
import { server } from '../../../test/mocks/server'
import { renderScreen } from '../../../test/test-utils'
import { ProductsScreen } from './ProductsScreen'

describe('ProductsScreen', () => {
  it('lists every product with its status, stock and category', async () => {
    stubAdminBackend()
    renderScreen(<ProductsScreen />)

    const lipstick = await screen.findByRole('link', { name: /Velvet Matte Lipstick/ })
    expect(lipstick).toHaveAttribute('href', '/admin/catalog/products/1')
    expect(lipstick).toHaveTextContent('On sale')
    expect(lipstick).toHaveTextContent('8 in stock')
    expect(lipstick).toHaveTextContent('LIP-VELVET · Lipstick')
    expect(screen.getByRole('link', { name: /Vitamin C Serum/ })).toHaveTextContent('Draft')
  })

  it('sends search and filters to the API', async () => {
    const backend = stubAdminBackend()
    renderScreen(<ProductsScreen />)
    await screen.findByRole('link', { name: /Velvet/ })

    await userEvent.type(screen.getByRole('searchbox', { name: /Search/ }), 'velvet')
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Status' }), 'archived')
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Category' }), '2')

    await waitFor(() => {
      const last = backend.requests.at(-1)!.search
      expect([last.get('q'), last.get('status'), last.get('category_id')]).toEqual([
        'velvet',
        'archived',
        '2',
      ])
    })
  })

  it('pages through long lists', async () => {
    const backend = stubAdminBackend()
    server.use(
      http.get(`${API}/internal/products`, ({ request }) => {
        backend.requests.push({
          method: 'GET',
          path: '/products',
          search: new URL(request.url).searchParams,
          body: null,
          headers: request.headers,
        })
        return HttpResponse.json({ items: adminProductList, total: 120 })
      }),
    )
    renderScreen(<ProductsScreen />)
    expect(await screen.findByText('1–50 of 120')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Next' }))

    expect(await screen.findByText('51–100 of 120')).toBeInTheDocument()
    expect(backend.requests.at(-1)!.search.get('offset')).toBe('50')
  })

  it('shows an empty state', async () => {
    stubAdminBackend()
    server.use(
      http.get(`${API}/internal/products`, () => HttpResponse.json({ items: [], total: 0 })),
    )
    renderScreen(<ProductsScreen />)

    expect(await screen.findByText('No products match.')).toBeInTheDocument()
  })
})
