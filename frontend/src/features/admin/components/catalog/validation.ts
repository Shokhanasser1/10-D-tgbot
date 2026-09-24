/** A price the API accepts: a non-negative amount with at most two decimals ("19", "19.9"). */
export function isPrice(value: string): boolean {
  return /^\d{1,8}(\.\d{1,2})?$/.test(value.trim())
}

/** A stock quantity: a whole number, which may be negative after an oversell. */
export function isStock(value: string): boolean {
  return /^-?\d{1,9}$/.test(value.trim())
}
