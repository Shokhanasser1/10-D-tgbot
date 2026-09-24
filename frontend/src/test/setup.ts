import '@testing-library/jest-dom/vitest'

import { cleanup } from '@testing-library/react'
import { afterAll, afterEach, beforeAll, vi } from 'vitest'

import { resetMapMock } from './mocks/reactLeaflet'
import { server } from './mocks/server'

// jsdom has no layout, so react-leaflet cannot render; every test gets the lightweight stand-in.
vi.mock('react-leaflet', () => import('./mocks/reactLeaflet'))

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))

afterEach(() => {
  cleanup()
  server.resetHandlers()
  resetMapMock()
})

afterAll(() => server.close())
