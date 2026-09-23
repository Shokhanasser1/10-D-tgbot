import '@fontsource-variable/inter-tight'
import './shared/styles/tokens.css'
import './shared/styles/global.css'

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { RouterProvider } from 'react-router-dom'

import { AppProviders } from './app/providers'
import { router } from './app/router'
import { initWebApp } from './shared/telegram/webApp'

initWebApp()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AppProviders>
      <RouterProvider router={router} />
    </AppProviders>
  </StrictMode>,
)
