import { ApiError } from '../../shared/api/client'

const KEY_BY_CODE: Record<string, string> = {
  shipment_taken: 'courier.errors.shipmentTaken',
  delivery_limit_reached: 'courier.errors.limitReached',
  invalid_state: 'courier.errors.invalidState',
}

function codeOf(error: ApiError): string | undefined {
  const detail = error.detail
  if (typeof detail === 'object' && detail !== null && 'code' in detail) {
    const { code } = detail as { code: unknown }
    return typeof code === 'string' ? code : undefined
  }
  return undefined
}

/** The i18n key to show for a failed courier action, from the API's stable `code`. */
export function courierErrorKey(error: unknown): string {
  if (!(error instanceof ApiError)) return 'common.error'

  const code = codeOf(error)
  if (code && code in KEY_BY_CODE) return KEY_BY_CODE[code]
  // Somebody else's delivery and a missing one are indistinguishable by design.
  if (error.status === 404) return 'courier.errors.gone'
  return 'common.error'
}

/** Not (or no longer) a courier: the account was deactivated while the app was open. */
export function isForbidden(error: unknown): boolean {
  return error instanceof ApiError && error.status === 403
}
