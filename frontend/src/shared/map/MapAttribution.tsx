import { openExternalLink } from '../telegram/webApp'
import { ATTRIBUTION, ATTRIBUTION_URL } from './config'
import styles from './MapView.module.css'

/**
 * Replaces Leaflet's own attribution control, whose link would navigate the Mini App's
 * WebView away from the app. Opening it through Telegram keeps the app where it is.
 */
export function MapAttribution() {
  return (
    <button
      type="button"
      className={styles.attribution}
      onClick={() => openExternalLink(ATTRIBUTION_URL)}
    >
      {ATTRIBUTION}
    </button>
  )
}
