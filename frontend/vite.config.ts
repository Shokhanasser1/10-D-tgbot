/// <reference types="vitest/config" />
import { fileURLToPath, URL } from 'node:url'

import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    // Pinned so tests never depend on a developer's local .env.
    env: {
      VITE_API_BASE_URL: 'http://api.test',
      VITE_STRIPE_PUBLISHABLE_KEY: 'pk_test_unit',
      VITE_DEV_MOCK_INIT_DATA: 'mock-init-data',
      VITE_MAP_TILE_URL: 'https://tiles.test/{z}/{x}/{y}.png',
      VITE_MAP_DEFAULT_CENTER: '41.3,69.2',
      VITE_MAP_ATTRIBUTION: 'Test map data',
    },
  },
})
