import { latLngBounds } from 'leaflet'
import { useEffect, useRef } from 'react'
import { Marker, Tooltip, useMap } from 'react-leaflet'

import { DEFAULT_CENTER } from '../../../shared/map/config'
import { courierIcon, staleCourierIcon } from '../../../shared/map/markerIcons'
import { MapView } from '../../../shared/map/MapView'
import type { CourierLocation } from '../types'

const FIT_PADDING: [number, number] = [40, 40]
const FIT_MAX_ZOOM = 15

/** Frames all couriers when the set of couriers changes; leaves the dispatcher's panning alone. */
function FitCouriers({ locations }: { locations: CourierLocation[] }) {
  const map = useMap()
  const framed = useRef('')

  useEffect(() => {
    const key = locations
      .map((l) => l.courier_id)
      .sort((a, b) => a - b)
      .join(',')
    if (locations.length === 0 || key === framed.current) return
    framed.current = key
    map.fitBounds(latLngBounds(locations.map((l) => [l.latitude, l.longitude])), {
      padding: FIT_PADDING,
      maxZoom: FIT_MAX_ZOOM,
    })
  }, [map, locations])

  return null
}

interface CouriersMapProps {
  locations: CourierLocation[]
  label: string
  className?: string
}

export function CouriersMap({ locations, label, className }: CouriersMapProps) {
  return (
    <MapView center={locations[0] ?? DEFAULT_CENTER} label={label} className={className}>
      <FitCouriers locations={locations} />
      {locations.map((location) => (
        <Marker
          key={location.courier_id}
          position={[location.latitude, location.longitude]}
          icon={location.is_stale ? staleCourierIcon : courierIcon}
          title={location.name}
        >
          <Tooltip>{location.name}</Tooltip>
        </Marker>
      ))}
    </MapView>
  )
}
