import { ApiError } from '../../shared/api/client'

const KEY_BY_CODE: Record<string, string> = {
  invalid_state: 'admin.errors.invalidState',
  last_owner: 'admin.errors.lastOwner',
  self_deactivation: 'admin.errors.selfDeactivation',
  already_exists: 'admin.errors.alreadyExists',
}

function codeOf(detail: unknown): string | undefined {
  if (typeof detail === 'object' && detail !== null && 'code' in detail) {
    const { code } = detail as { code: unknown }
    return typeof code === 'string' ? code : undefined
  }
  return undefined
}

/** The i18n key for a failed admin action, from the API's stable `code` or its status. */
export function adminErrorKey(error: unknown): string {
  if (!(error instanceof ApiError)) return 'common.error'
  const code = codeOf(error.detail)
  if (code && code in KEY_BY_CODE) return KEY_BY_CODE[code]
  switch (error.status) {
    case 400:
      // Duplicate SKUs/slugs and rejected images both land here.
      return 'admin.errors.badRequest'
    case 403:
      return 'admin.errors.forbidden'
    case 404:
      return 'admin.errors.notFound'
    case 409:
      return 'admin.errors.conflict'
    case 413:
      return 'admin.errors.tooLarge'
    case 422:
      return 'admin.errors.invalid'
    default:
      return 'common.error'
  }
}

export function isStatus(error: unknown, status: number): boolean {
  return error instanceof ApiError && error.status === status
}
