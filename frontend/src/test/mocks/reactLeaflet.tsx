import { latLng } from 'leaflet'
import type { ReactNode } from 'react'
import { act } from 'react'
import { vi } from 'vitest'

/**
 * Stand-in for react-leaflet, which needs real layout that jsdom does not have. It is installed
 * for every test from setup.ts; tests drive it through `fireMapClick` and inspect `mapApi`.
 * Real Leaflet is still used for what does not need layout (`latLng`, `divIcon`, bounds).
 */

type ClickHandler = (event: { latlng: ReturnType<typeof latLng> }) => void

let handlers: { click?: ClickHandler } = {}

export const mapApi = {
  setView: vi.fn(),
  panTo: vi.fn(),
  fitBounds: vi.fn(),
  invalidateSize: vi.fn(),
  getZoom: vi.fn(() => 13),
  getContainer: vi.fn(() => document.createElement('div')),
  getBounds: vi.fn(() => ({ contains: vi.fn(() => true) })),
}

export function resetMapMock(): void {
  handlers = {}
  for (const fn of Object.values(mapApi)) fn.mockClear()
  mapApi.getZoom.mockImplementation(() => 13)
  mapApi.getBounds.mockImplementation(() => ({ contains: vi.fn(() => true) }))
}

/** Simulates a tap on the map at the given position, with Leaflet's real LatLng semantics. */
export function fireMapClick(lat: number, lng: number): void {
  act(() => handlers.click?.({ latlng: latLng(lat, lng) }))
}

export function MapContainer({
  children,
  center,
}: {
  children?: ReactNode
  center: [number, number]
}) {
  return (
    <div data-testid="map" data-center={center.join(',')}>
      {children}
    </div>
  )
}

export function TileLayer({ url }: { url: string }) {
  return <div data-testid="tile-layer" data-url={url} />
}

export function Marker({
  position,
  icon,
  title,
  children,
}: {
  position: [number, number]
  icon?: { options: { html?: string | HTMLElement | false } }
  title?: string
  children?: ReactNode
}) {
  return (
    <div
      data-testid="marker"
      data-position={position.join(',')}
      data-icon={typeof icon?.options.html === 'string' ? icon.options.html : ''}
      title={title}
    >
      {children}
    </div>
  )
}

export function Tooltip({ children }: { children?: ReactNode }) {
  return <span>{children}</span>
}

export function useMap() {
  return mapApi
}

export function useMapEvents(registered: { click?: ClickHandler }) {
  handlers = registered
  return mapApi
}
