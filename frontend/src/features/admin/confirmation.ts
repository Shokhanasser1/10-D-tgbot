import { ApiError } from '../../shared/api/client'

/**
 * Money and admin management need the password re-entered (Spec 7). An admin request that the
 * API refuses with `password_confirmation_required` asks the registered handler (the password
 * dialog) and, once the password is confirmed, is sent again exactly once.
 */
type Handler = () => Promise<boolean>

let handler: Handler | null = null

export function setConfirmationHandler(next: Handler | null): void {
  handler = next
}

export function errorCode(error: unknown): string | undefined {
  if (!(error instanceof ApiError)) return undefined
  const detail = error.detail
  if (typeof detail === 'object' && detail !== null && 'code' in detail) {
    const { code } = detail as { code: unknown }
    return typeof code === 'string' ? code : undefined
  }
  return undefined
}

export async function withConfirmation<T>(run: () => Promise<T>): Promise<T> {
  try {
    return await run()
  } catch (error) {
    if (handler && errorCode(error) === 'password_confirmation_required' && (await handler())) {
      return run()
    }
    throw error
  }
}
