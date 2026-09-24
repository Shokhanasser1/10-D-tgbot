import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { MapAttribution } from './MapAttribution'

afterEach(() => {
  delete window.Telegram
  vi.restoreAllMocks()
})

describe('MapAttribution', () => {
  it('shows the configured attribution text', () => {
    render(<MapAttribution />)

    expect(screen.getByRole('button', { name: 'Test map data' })).toBeInTheDocument()
  })

  it('opens the copyright page through Telegram instead of navigating the app away', async () => {
    const openLink = vi.fn()
    window.Telegram = { WebApp: { initData: 'x', openLink } } as unknown as Window['Telegram']
    render(<MapAttribution />)

    await userEvent.click(screen.getByRole('button', { name: 'Test map data' }))

    expect(openLink).toHaveBeenCalledWith('https://www.openstreetmap.org/copyright')
  })

  it('opens a separate tab in a plain browser', async () => {
    const windowOpen = vi.spyOn(window, 'open').mockReturnValue(null)
    render(<MapAttribution />)

    await userEvent.click(screen.getByRole('button', { name: 'Test map data' }))

    expect(windowOpen).toHaveBeenCalledWith(
      'https://www.openstreetmap.org/copyright',
      '_blank',
      'noopener',
    )
  })
})
