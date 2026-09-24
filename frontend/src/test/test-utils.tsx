import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import type { ReactElement, ReactNode } from 'react'
import { I18nextProvider } from 'react-i18next'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import i18n from '../shared/i18n'

interface RenderScreenOptions {
  /** URL the memory router starts at. */
  route?: string
  /** Route pattern the screen is mounted on (needed for useParams). */
  path?: string
  /** Extra routes, used to assert that the screen navigated somewhere. */
  extraRoutes?: { path: string; element: ReactNode }[]
}

export function renderScreen(
  ui: ReactElement,
  { route = '/', path = '/', extraRoutes = [] }: RenderScreenOptions = {},
) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <I18nextProvider i18n={i18n}>
        <MemoryRouter initialEntries={[route]}>
          <Routes>
            <Route path={path} element={ui} />
            {extraRoutes.map((extra) => (
              <Route key={extra.path} path={extra.path} element={extra.element} />
            ))}
          </Routes>
        </MemoryRouter>
      </I18nextProvider>
    </QueryClientProvider>,
  )
}
