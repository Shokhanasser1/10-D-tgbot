import { latLngBounds } from 'leaflet'
import { useEffect, useRef } from 'react'
import { Marker, useMap } from 'react-leaflet'

import type { Coordinates } from '../types'
import { DEFAULT_CENTER } from './config'
import { courierIcon, destinationIcon, staleCourierIcon } from './markerIcons'
import { MapView } from './MapView'

export interface CourierPosition extends Coordinates {
  isStale: boolean
}

interface TrackingMapProps {
  courier: CourierPosition | null
  destination: Coordinates | null
  label: string
  className?: string
}

const FIT_PADDING: [number, number] = [40, 40]
const FIT_MAX_ZOOM = 16

const toPoint = ({ latitude, longitude }: Coordinates): [number, number] => [latitude, longitude]

/**
 * Frames the map on the points shown, once per set of points. A courier who first appears on a
 * map that only showed the destination triggers one more framing; after that the map is left
 * alone so it never fights the customer's own panning and zooming.
 */
function FitOnce({ courier, destination }: Pick<TrackingMapProps, 'courier' | 'destination'>) {
  const map = useMap()
  const framed = useRef('')

  useEffect(() => {
    const points = [courier, destination].filter((point): point is Coordinates => point !== null)
    const key = `${courier ? 'c' : ''}${destination ? 'd' : ''}`
    if (points.length === 0 || key === framed.current) return
    framed.current = key

    if (points.length === 1) {
      map.setView(toPoint(points[0]), FIT_MAX_ZOOM - 1)
    } else {
      map.fitBounds(latLngBounds(points.map(toPoint)), {
        padding: FIT_PADDING,
        maxZoom: FIT_MAX_ZOOM,
      })
    }
  }, [map, courier, destination])

  return null
}

/** Keeps a moving courier in view, but only pans when they have left the visible area. */
function KeepCourierVisible({ courier }: { courier: CourierPosition | null }) {
  const map = useMap()
  const latitude = courier?.latitude
  const longitude = courier?.longitude

  useEffect(() => {
    if (latitude === undefined || longitude === undefined) return
    if (!map.getBounds().contains([latitude, longitude])) map.panTo([latitude, longitude])
  }, [map, latitude, longitude])

  return null
}

export function TrackingMap({ courier, destination, label, className }: TrackingMapProps) {
  return (
    <MapView center={courier ?? destination ?? DEFAULT_CENTER} label={label} className={className}>
      <FitOnce courier={courier} destination={destination} />
      <KeepCourierVisible courier={courier} />
      {destination && <Marker position={toPoint(destination)} icon={destinationIcon} />}
      {courier && (
        <Marker
          position={toPoint(courier)}
          icon={courier.isStale ? staleCourierIcon : courierIcon}
        />
      )}
    </MapView>
  )
}
