import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { products } from '../../../test/fixtures'
import { API } from '../../../test/mocks/handlers'
import { server } from '../../../test/mocks/server'
import { renderScreen } from '../../../test/test-utils'
import { CatalogHomeScreen } from './CatalogHomeScreen'

describe('CatalogHomeScreen', () => {
  it('lists products and categories from the API', async () => {
    renderScreen(<CatalogHomeScreen />)

    expect(await screen.findByText('Velvet Matte Lipstick')).toBeInTheDocument()
    expect(screen.getByText('Vitamin C Serum')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Serums' })).toBeInTheDocument()
  })

  it('narrows the list when a category is selected', async () => {
    const user = userEvent.setup()
    renderScreen(<CatalogHomeScreen />)
    await screen.findByText('Velvet Matte Lipstick')

    await user.click(screen.getByRole('button', { name: 'Serums' }))

    await waitFor(() => expect(screen.queryByText('Velvet Matte Lipstick')).not.toBeInTheDocument())
    expect(screen.getByText('Vitamin C Serum')).toBeInTheDocument()
  })

  it('filters by the search box without another request', async () => {
    const user = userEvent.setup()
    renderScreen(<CatalogHomeScreen />)
    await screen.findByText('Velvet Matte Lipstick')

    await user.type(screen.getByPlaceholderText('Search products'), 'vitamin')

    expect(screen.queryByText('Velvet Matte Lipstick')).not.toBeInTheDocument()
    expect(screen.getByText('Vitamin C Serum')).toBeInTheDocument()
  })

  it('shows the empty state when nothing matches the search', async () => {
    const user = userEvent.setup()
    renderScreen(<CatalogHomeScreen />)
    await screen.findByText('Velvet Matte Lipstick')

    await user.type(screen.getByPlaceholderText('Search products'), 'zzz')

    expect(screen.getByText('No products found')).toBeInTheDocument()
  })

  // Regression: a failed request used to render the same "empty" state as an empty catalog.
  it('shows an error with retry, not the empty state, when loading fails', async () => {
    const user = userEvent.setup()
    server.use(http.get(`${API}/catalog/products`, () => new HttpResponse(null, { status: 500 })))
    renderScreen(<CatalogHomeScreen />)

    expect(await screen.findByText('Something went wrong')).toBeInTheDocument()
    expect(screen.queryByText('No products found')).not.toBeInTheDocument()

    server.use(http.get(`${API}/catalog/products`, () => HttpResponse.json(products)))
    await user.click(screen.getByRole('button', { name: 'Try again' }))

    expect(await screen.findByText('Velvet Matte Lipstick')).toBeInTheDocument()
  })
})

describe('CatalogHomeScreen: sellers (Spec 9)', () => {
  it("shows each product's seller", async () => {
    renderScreen(<CatalogHomeScreen />)

    expect(await screen.findByText('Lola Beauty')).toBeInTheDocument()
    expect(screen.getByText('Anor')).toBeInTheDocument()
  })

  it("lists one seller's products and clears the filter", async () => {
    const user = userEvent.setup()
    renderScreen(<CatalogHomeScreen />, { route: '/?seller=8' })

    expect(await screen.findByText('Products of Anor')).toBeInTheDocument()
    expect(screen.getByText('Vitamin C Serum')).toBeInTheDocument()
    expect(screen.queryByText('Velvet Matte Lipstick')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Show all products' }))

    expect(await screen.findByText('Velvet Matte Lipstick')).toBeInTheDocument()
    expect(screen.queryByText('Products of Anor')).not.toBeInTheDocument()
  })
})
