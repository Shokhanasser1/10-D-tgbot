import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Marker, useMap, useMapEvents } from 'react-leaflet'

import type { Coordinates } from '../types'
import { PillButton } from '../ui/PillButton'
import { DEFAULT_CENTER } from './config'
import { destinationIcon } from './markerIcons'
import styles from './MapPicker.module.css'
import { MapView } from './MapView'

interface MapPickerProps {
  value: Coordinates | null
  onChange: (value: Coordinates | null) => void
}

type LocateState = 'idle' | 'locating' | 'failed'

const GEOLOCATION_TIMEOUT_MS = 10_000
const PIN_ZOOM = 16

// Six decimals is about 11 cm, far finer than a doorstep needs and stable in a JSON round-trip.
const round = (value: number) => Math.round(value * 1e6) / 1e6

function ClickToPlace({ onPick }: { onPick: (pin: Coordinates) => void }) {
  useMapEvents({
    click(event) {
      // Leaflet does not normalise longitude, so a click on a repeated copy of the world would
      // otherwise produce a value the API rejects (e.g. 190 instead of -170).
      const { lat, lng } = event.latlng.wrap()
      onPick({ latitude: round(lat), longitude: round(lng) })
    },
  })
  return null
}

function FocusOn({ target }: { target: Coordinates | null }) {
  const map = useMap()

  useEffect(() => {
    if (target) map.setView([target.latitude, target.longitude], Math.max(map.getZoom(), PIN_ZOOM))
  }, [map, target])

  return null
}

export function MapPicker({ value, onChange }: MapPickerProps) {
  const { t } = useTranslation()
  const [locateState, setLocateState] = useState<LocateState>('idle')
  const [focus, setFocus] = useState<Coordinates | null>(null)

  function locateMe() {
    if (!('geolocation' in navigator)) {
      setLocateState('failed')
      return
    }
    setLocateState('locating')
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        const pin = { latitude: round(coords.latitude), longitude: round(coords.longitude) }
        onChange(pin)
        setFocus(pin)
        setLocateState('idle')
      },
      () => setLocateState('failed'),
      { timeout: GEOLOCATION_TIMEOUT_MS, maximumAge: 60_000 },
    )
  }

  return (
    <section className={styles.picker}>
      <h2 className={styles.title}>{t('checkout.map.title')}</h2>
      <p className={styles.hint}>{t('checkout.map.hint')}</p>
      <MapView
        center={value ?? DEFAULT_CENTER}
        zoom={value ? PIN_ZOOM : 12}
        label={t('checkout.map.label')}
      >
        <ClickToPlace onPick={onChange} />
        <FocusOn target={focus} />
        {value && <Marker position={[value.latitude, value.longitude]} icon={destinationIcon} />}
      </MapView>
      <div className={styles.actions}>
        <PillButton
          variant="secondary"
          className={styles.action}
          onClick={locateMe}
          disabled={locateState === 'locating'}
        >
          {locateState === 'locating'
            ? t('checkout.map.locating')
            : t('checkout.map.useMyLocation')}
        </PillButton>
        {value && (
          <PillButton variant="secondary" className={styles.action} onClick={() => onChange(null)}>
            {t('checkout.map.removePin')}
          </PillButton>
        )}
      </div>
      {locateState === 'failed' && (
        <p role="status" className={styles.hint}>
          {t('checkout.map.locationFailed')}
        </p>
      )}
      {value && (
        <p role="status" className={styles.hint}>
          {t('checkout.map.pinPlaced')}
        </p>
      )}
    </section>
  )
}
