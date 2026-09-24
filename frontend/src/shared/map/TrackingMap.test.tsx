import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { mapApi } from '../../test/mocks/reactLeaflet'
import { TrackingMap } from './TrackingMap'

const destination = { latitude: 52.52, longitude: 13.405 }
const courier = { latitude: 52.5, longitude: 13.4, isStale: false }

function renderMap(props: Partial<Parameters<typeof TrackingMap>[0]> = {}) {
  return render(<TrackingMap courier={courier} destination={destination} label="Map" {...props} />)
}

describe('TrackingMap', () => {
  it('shows the courier and the destination', () => {
    renderMap()

    expect(screen.getAllByTestId('marker').map((m) => m.getAttribute('data-position'))).toEqual([
      '52.52,13.405',
      '52.5,13.4',
    ])
    expect(screen.getByRole('group', { name: 'Map' })).toBeInTheDocument()
  })

  it('shows nothing but the map when there is neither', () => {
    renderMap({ courier: null, destination: null })

    expect(screen.queryByTestId('marker')).not.toBeInTheDocument()
    expect(screen.getByTestId('map')).toHaveAttribute('data-center', '41.3,69.2')
    expect(mapApi.fitBounds).not.toHaveBeenCalled()
    expect(mapApi.setView).not.toHaveBeenCalled()
  })

  it('draws a stale courier differently', () => {
    const { rerender } = renderMap()
    const live = screen.getAllByTestId('marker')[1].getAttribute('data-icon')

    rerender(
      <TrackingMap courier={{ ...courier, isStale: true }} destination={destination} label="Map" />,
    )

    expect(screen.getAllByTestId('marker')[1].getAttribute('data-icon')).not.toEqual(live)
  })

  it('frames both points once', () => {
    renderMap()

    expect(mapApi.fitBounds).toHaveBeenCalledTimes(1)
    expect(mapApi.fitBounds.mock.calls[0][1]).toMatchObject({ maxZoom: 16 })
  })

  it('does not reframe the map while the courier moves, so it never fights the customer', () => {
    const { rerender } = renderMap()

    rerender(
      <TrackingMap
        courier={{ ...courier, latitude: 52.51 }}
        destination={destination}
        label="Map"
      />,
    )

    expect(mapApi.fitBounds).toHaveBeenCalledTimes(1)
    expect(mapApi.setView).not.toHaveBeenCalled()
  })

  it('centres on a lone destination, then reframes once when the courier first appears', () => {
    const { rerender } = renderMap({ courier: null })
    expect(mapApi.setView).toHaveBeenCalledWith([52.52, 13.405], 15)
    expect(mapApi.fitBounds).not.toHaveBeenCalled()

    rerender(<TrackingMap courier={courier} destination={destination} label="Map" />)

    expect(mapApi.fitBounds).toHaveBeenCalledTimes(1)
  })

  it('centres on a lone courier when there is no destination pin', () => {
    renderMap({ destination: null })

    expect(mapApi.setView).toHaveBeenCalledWith([52.5, 13.4], 15)
  })

  it('pans to a courier who has left the visible area', () => {
    const { rerender } = renderMap()
    mapApi.panTo.mockClear()
    mapApi.getBounds.mockImplementation(() => ({ contains: vi.fn(() => false) }))

    rerender(
      <TrackingMap courier={{ ...courier, latitude: 53 }} destination={destination} label="Map" />,
    )

    expect(mapApi.panTo).toHaveBeenCalledWith([53, 13.4])
  })

  it('leaves the map alone while the courier stays in view', () => {
    const { rerender } = renderMap()
    mapApi.panTo.mockClear()

    rerender(
      <TrackingMap
        courier={{ ...courier, latitude: 52.505 }}
        destination={destination}
        label="Map"
      />,
    )

    expect(mapApi.panTo).not.toHaveBeenCalled()
  })
})
