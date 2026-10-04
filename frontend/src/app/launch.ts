/**
 * Spec 8 §4: a Mini App opened at the bare root sends each role to its own screen. The rule
 * runs once per page load; a notification's deep link, or coming back to `/` later through
 * the Shop button, never redirects.
 */

export type LaunchDecision = 'deciding' | 'admin' | 'courier' | 'shop'

/** After this long without an answer, a role check counts as "no role". */
export const LAUNCH_TIMEOUT_MS = 3000

let pending = false

/** main.tsx calls this once, with the path the Mini App was opened at. */
export function startLaunch(openedAt: string): void {
  pending = openedAt === '/'
}

export function isLaunchPending(): boolean {
  return pending
}

export function finishLaunch(): void {
  pending = false
}

/**
 * Admin outranks courier, courier outranks the shop. `undefined` means that check has not
 * answered yet: wait for it, unless the timeout has passed, after which it counts as "no".
 * A failed check arrives here as `false`.
 */
export function decideLaunch(
  isAdmin: boolean | undefined,
  isCourier: boolean | undefined,
  timedOut: boolean,
): LaunchDecision {
  if (isAdmin) return 'admin'
  if (isAdmin === undefined && !timedOut) return 'deciding'
  if (isCourier) return 'courier'
  if (isCourier === undefined && !timedOut) return 'deciding'
  return 'shop'
}
