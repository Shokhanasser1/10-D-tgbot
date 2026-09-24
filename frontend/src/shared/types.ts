export interface DeliveryAddress {
  street: string
  city: string
  postal_code: string
  country: string
  phone: string
  notes?: string | null
  /** Optional pin the customer dropped on the map; always given together. */
  latitude?: number | null
  longitude?: number | null
}

export interface Coordinates {
  latitude: number
  longitude: number
}
