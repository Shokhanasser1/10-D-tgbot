import { divIcon } from 'leaflet'

import styles from './markers.module.css'

// Every marker gets one of these explicitly. Leaflet's default icon loads its PNGs by guessing
// their URL from the stylesheet, which a bundler breaks, and its default `divIcon` class draws
// a white square, so both are avoided by naming our own class.
export const destinationIcon = divIcon({
  className: styles.marker,
  html: `<span class="${styles.destination}"></span>`,
  iconSize: [32, 32],
  iconAnchor: [16, 30],
})

export const courierIcon = divIcon({
  className: styles.marker,
  html: `<span class="${styles.courier}"></span>`,
  iconSize: [32, 32],
  iconAnchor: [16, 16],
})

export const staleCourierIcon = divIcon({
  className: styles.marker,
  html: `<span class="${styles.courierStale}"></span>`,
  iconSize: [32, 32],
  iconAnchor: [16, 16],
})
