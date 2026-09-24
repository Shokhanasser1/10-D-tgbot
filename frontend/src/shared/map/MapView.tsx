import 'leaflet/dist/leaflet.css'

import { type ReactNode, useEffect } from 'react'
import { MapContainer, TileLayer, useMap } from 'react-leaflet'

import { useDisableVerticalSwipes } from '../telegram/hooks'
import type { Coordinates } from '../types'
import { TILE_URL } from './config'
import { MapAttribution } from './MapAttribution'
import styles from './MapView.module.css'

interface MapViewProps {
  center: Coordinates
  zoom?: number
  label: string
  className?: string
  children?: ReactNode
}

/** Leaflet measures its container once; tell it when a layout change resizes it. */
function InvalidateSizeOnResize() {
  const map = useMap()

  useEffect(() => {
    if (typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(() => map.invalidateSize())
    observer.observe(map.getContainer())
    return () => observer.disconnect()
  }, [map])

  return null
}

export function MapView({ center, zoom = 13, label, className, children }: MapViewProps) {
  useDisableVerticalSwipes()

  return (
    <div
      role="group"
      aria-label={label}
      className={[styles.wrapper, className].filter(Boolean).join(' ')}
    >
      <MapContainer
        center={[center.latitude, center.longitude]}
        zoom={zoom}
        className={styles.map}
        attributionControl={false}
        zoomControl
      >
        <TileLayer url={TILE_URL} maxZoom={19} noWrap />
        <InvalidateSizeOnResize />
        {children}
      </MapContainer>
      <MapAttribution />
    </div>
  )
}
