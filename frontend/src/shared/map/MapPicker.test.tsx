import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { fireMapClick, mapApi } from '../../test/mocks/reactLeaflet'
import { renderScreen } from '../../test/test-utils'
import type { Coordinates } from '../types'
import { MapPicker } from './MapPicker'

/** Owns the pin the way AddressForm does, so the UI reacts to what the picker reports. */
function Harness({ onChange }: { onChange: (pin: Coordinates | null) => void }) {
  const [pin, setPin] = useState<Coordinates | null>(null)
  return (
    <MapPicker
      value={pin}
      onChange={(next) => {
        setPin(next)
        onChange(next)
      }}
    />
  )
}

function stubGeolocation(getCurrentPosition?: (...args: unknown[]) => void) {
  Object.defineProperty(navigator, 'geolocation', {
    configurable: true,
    value: getCurrentPosition ? { getCurrentPosition } : undefined,
  })
}

afterEach(() => {
  // jsdom has no geolocation; put the environment back the way it was found.
  Reflect.deleteProperty(navigator, 'geolocation')
})

describe('MapPicker', () => {
  it('opens on the configured centre with no marker when nothing is pinned', () => {
    renderScreen(<Harness onChange={vi.fn()} />)

    expect(screen.getByTestId('map')).toHaveAttribute('data-center', '41.3,69.2')
    expect(screen.queryByTestId('marker')).not.toBeInTheDocument()
    expect(screen.getByTestId('tile-layer')).toHaveAttribute(
      'data-url',
      'https://tiles.test/{z}/{x}/{y}.png',
    )
  })

  it('opens on an existing pin', () => {
    renderScreen(<MapPicker value={{ latitude: 52.5, longitude: 13.4 }} onChange={vi.fn()} />)

    expect(screen.getByTestId('map')).toHaveAttribute('data-center', '52.5,13.4')
    expect(screen.getByTestId('marker')).toHaveAttribute('data-position', '52.5,13.4')
  })

  it('places a pin where the map is tapped, rounded to six decimals', () => {
    const onChange = vi.fn()
    renderScreen(<Harness onChange={onChange} />)

    fireMapClick(52.123456789, 13.987654321)

    expect(onChange).toHaveBeenLastCalledWith({ latitude: 52.123457, longitude: 13.987654 })
    expect(screen.getByTestId('marker')).toHaveAttribute('data-position', '52.123457,13.987654')
    expect(screen.getByText('Pin placed on the map.')).toBeInTheDocument()
  })

  // Regression: Leaflet reports 190 for a tap on the next copy of the world; the API accepts
  // ±180 only, so the value has to be wrapped before it is stored.
  it.each([
    [190, -170],
    [-190, 170],
    [540, -180],
    [13.4, 13.4],
  ])('wraps a tapped longitude of %d to %d', (tapped, stored) => {
    const onChange = vi.fn()
    renderScreen(<Harness onChange={onChange} />)

    fireMapClick(10, tapped)

    expect(onChange).toHaveBeenLastCalledWith({ latitude: 10, longitude: stored })
  })

  it('moves the pin when the map is tapped again', () => {
    const onChange = vi.fn()
    renderScreen(<Harness onChange={onChange} />)

    fireMapClick(10, 20)
    fireMapClick(11, 21)

    expect(onChange).toHaveBeenLastCalledWith({ latitude: 11, longitude: 21 })
    expect(screen.getAllByTestId('marker')).toHaveLength(1)
  })

  it('removes the pin', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    renderScreen(<Harness onChange={onChange} />)
    expect(screen.queryByRole('button', { name: 'Remove pin' })).not.toBeInTheDocument()
    fireMapClick(10, 20)

    await user.click(screen.getByRole('button', { name: 'Remove pin' }))

    expect(onChange).toHaveBeenLastCalledWith(null)
    expect(screen.queryByTestId('marker')).not.toBeInTheDocument()
  })

  it('uses the device location and moves the map there', async () => {
    const user = userEvent.setup()
    stubGeolocation((onSuccess: unknown) =>
      (onSuccess as (position: unknown) => void)({
        coords: { latitude: 41.2995123456, longitude: 69.2401234567 },
      }),
    )
    const onChange = vi.fn()
    renderScreen(<Harness onChange={onChange} />)

    await user.click(screen.getByRole('button', { name: 'Use my location' }))

    expect(onChange).toHaveBeenLastCalledWith({ latitude: 41.299512, longitude: 69.240123 })
    expect(mapApi.setView).toHaveBeenCalledWith([41.299512, 69.240123], 16)
  })

  it('asks for the location with a timeout, so it can never hang the form', async () => {
    const user = userEvent.setup()
    const getCurrentPosition = vi.fn()
    stubGeolocation(getCurrentPosition)
    renderScreen(<Harness onChange={vi.fn()} />)

    await user.click(screen.getByRole('button', { name: 'Use my location' }))

    expect(getCurrentPosition.mock.calls[0][2]).toMatchObject({ timeout: 10_000 })
    expect(screen.getByRole('button', { name: 'Finding you…' })).toBeDisabled()
  })

  it('explains a refusal and still lets the customer tap the map', async () => {
    const user = userEvent.setup()
    stubGeolocation((_ok: unknown, onError: unknown) => (onError as () => void)())
    const onChange = vi.fn()
    renderScreen(<Harness onChange={onChange} />)

    await user.click(screen.getByRole('button', { name: 'Use my location' }))
    expect(screen.getByText(/Couldn't get your location/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Use my location' })).toBeEnabled()

    fireMapClick(10, 20)
    expect(onChange).toHaveBeenLastCalledWith({ latitude: 10, longitude: 20 })
  })

  it('explains when the device has no geolocation at all', async () => {
    const user = userEvent.setup()
    stubGeolocation(undefined)
    Reflect.deleteProperty(navigator, 'geolocation')
    renderScreen(<Harness onChange={vi.fn()} />)

    await user.click(screen.getByRole('button', { name: 'Use my location' }))

    expect(screen.getByText(/Couldn't get your location/)).toBeInTheDocument()
  })
})
