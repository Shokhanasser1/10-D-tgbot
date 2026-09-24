import type { Coordinates } from '../types'

const DEFAULT_TILE_URL = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
const DEFAULT_ATTRIBUTION = '© OpenStreetMap contributors'
const FALLBACK_CENTER: Coordinates = { latitude: 52.52, longitude: 13.405 }

/** Where a link from the attribution text leads (the data is OpenStreetMap's whichever tiles). */
export const ATTRIBUTION_URL = 'https://www.openstreetmap.org/copyright'

/**
 * Docker build args reach Vite as empty strings rather than `undefined`, so an unset setting has
 * to fall back on emptiness, not just absence (`??` would keep the empty string).
 */
export function settingOrDefault(raw: string | undefined, fallback: string): string {
  return raw?.trim() || fallback
}

/** Parses "lat,lng"; anything malformed or out of range yields the fallback. */
export function parseMapCenter(raw: string | undefined): Coordinates {
  const parts = (raw ?? '').split(',')
  if (parts.length !== 2 || parts.some((part) => part.trim() === '')) return FALLBACK_CENTER

  const [latitude, longitude] = parts.map(Number)
  const valid =
    Number.isFinite(latitude) &&
    Number.isFinite(longitude) &&
    Math.abs(latitude) <= 90 &&
    Math.abs(longitude) <= 180
  return valid ? { latitude, longitude } : FALLBACK_CENTER
}

// The public OSM tile server is for light use only; point VITE_MAP_TILE_URL at a real
// provider before sending real traffic through it.
export const TILE_URL = settingOrDefault(import.meta.env.VITE_MAP_TILE_URL, DEFAULT_TILE_URL)
export const ATTRIBUTION = settingOrDefault(
  import.meta.env.VITE_MAP_ATTRIBUTION,
  DEFAULT_ATTRIBUTION,
)
export const DEFAULT_CENTER = parseMapCenter(import.meta.env.VITE_MAP_DEFAULT_CENTER)
