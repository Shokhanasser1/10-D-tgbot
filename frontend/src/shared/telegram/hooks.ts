import { useEffect } from 'react'

import { getWebApp } from './webApp'

interface UseMainButtonOptions {
  text: string
  onClick: () => void
  visible?: boolean
  enabled?: boolean
}

export function useMainButton({
  text,
  onClick,
  visible = true,
  enabled = true,
}: UseMainButtonOptions): void {
  useEffect(() => {
    const mainButton = getWebApp()?.MainButton
    if (!mainButton) return

    mainButton.setText(text)
    if (enabled) mainButton.enable()
    else mainButton.disable()
    if (visible) mainButton.show()
    else mainButton.hide()
    mainButton.onClick(onClick)

    return () => {
      mainButton.offClick(onClick)
      mainButton.hide()
    }
  }, [text, onClick, visible, enabled])
}

export function useBackButton(onClick: () => void, visible = true): void {
  useEffect(() => {
    const backButton = getWebApp()?.BackButton
    if (!backButton) return

    if (visible) backButton.show()
    else backButton.hide()
    backButton.onClick(onClick)

    return () => {
      backButton.offClick(onClick)
      backButton.hide()
    }
  }, [onClick, visible])
}

/**
 * Stops a downward swipe from collapsing the Mini App while it is mounted. Without this,
 * dragging a map (or anything else pan-based) down would minimise the whole app.
 */
export function useDisableVerticalSwipes(): void {
  useEffect(() => {
    const webApp = getWebApp()
    if (!webApp?.disableVerticalSwipes || !webApp.isVersionAtLeast?.('7.7')) return

    webApp.disableVerticalSwipes()
    return () => webApp.enableVerticalSwipes?.()
  }, [])
}
