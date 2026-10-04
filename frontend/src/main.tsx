import '@fontsource-variable/inter-tight'
import './shared/styles/tokens.css'
import './shared/styles/global.css'

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { RouterProvider } from 'react-router-dom'

import { startLaunch } from './app/launch'
import { AppProviders } from './app/providers'
import { router } from './app/router'
import { initWebApp } from './shared/telegram/webApp'

initWebApp()
// Telegram opens the bare root (initData rides in the hash); notification buttons open deeper
// paths, which must not be redirected.
startLaunch(window.location.pathname)

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AppProviders>
      <RouterProvider router={router} />
    </AppProviders>
  </StrictMode>,
)
