# Role-based Launch Implementation Plan

> **For agentic workers:** implement task by task, in order; each task ends green and committed. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Opening the bot sends an admin to `/admin`, a courier to `/courier`, and everyone else to the shop; each role screen has a way back to the shop (Spec 8).

**Architecture:** Frontend only. A tiny module (`app/launch.ts`) remembers whether this page load started at `/` and holds the pure decision rule. A `LaunchGate` wraps the shop's layout route: on a launch at `/` it shows a skeleton, waits for the two role checks the shell already makes (`useIsAdmin`, `useCourierProfile`, shared through the react-query cache), then redirects or renders the shop. `/courier` moves out of the shop shell into a `CourierShell` with **Shop** / **Admin** buttons; the admin header gets **Shop** / **Courier** buttons.

**Tech Stack:** React 19, TypeScript strict, react-router v7 (`createBrowserRouter`), @tanstack/react-query v5, react-i18next (en/ru/uz), lucide-react icons, CSS Modules, Vitest + Testing Library + MSW v2.

Spec: `docs/superpowers/specs/2026-10-04-role-based-launch-design.md`.

## Global Constraints

- **No backend, bot or database change.** Deploy is `npm --prefix frontend run deploy:pages` only.
- Launch priority: admin → `/admin`; else courier → `/courier`; else the shop. Redirects use `replace`.
- The rule runs once per page load and only when the app was opened at the bare path `/`.
- A failed check, or one with no answer after **3000 ms**, counts as "no role". A late answer never redirects.
- New string `nav.shop`: en `"Shop"`, ru `"Магазин"`, uz `"Do'kon"`. Courier and admin buttons reuse `courier.nav` and `admin.open`.
- Style: prettier (no semicolons, single quotes, width 100), oxlint, TS strict, CSS Modules; comments say *why*.
- Tests: MSW runs with `onUnhandledRequest: 'error'`; the default handlers (`src/test/mocks/handlers.ts`) already answer `/courier/me` and `/internal/me` with 403, i.e. a plain customer.
- Commands below run from `frontend/`. Commit format: `<type>(frontend): <description>` with the
  `Co-Authored-By` trailer the session asks for.

## File map

| File | Status | Responsibility |
|---|---|---|
| `frontend/src/app/launch.ts` | create | once-per-load flag (`startLaunch`, `isLaunchPending`, `finishLaunch`) and the pure rule `decideLaunch` |
| `frontend/src/app/launch.test.ts` | create | table test of `decideLaunch` and the flag |
| `frontend/src/app/LaunchGate.tsx` | create | skeleton → redirect or shop, timeout |
| `frontend/src/app/LaunchGate.module.css` | create | skeleton layout |
| `frontend/src/app/LaunchGate.test.tsx` | create | launch behaviour against MSW |
| `frontend/src/app/CourierShell.tsx` | create | top bar for `/courier`: Shop, Admin (admins only) |
| `frontend/src/app/CourierShell.test.tsx` | create | its buttons |
| `frontend/src/shared/i18n/locales/{en,ru,uz}.json` | modify | `nav.shop` |
| `frontend/src/app/router.tsx` | modify | `/courier` top-level under `CourierShell`; `LaunchGate` around `AppShell` |
| `frontend/src/main.tsx` | modify | `startLaunch(window.location.pathname)` |
| `frontend/src/features/admin/components/AdminLayout.tsx` | modify | header buttons Shop, Courier (couriers only) |
| `frontend/src/features/admin/AdminApp.test.tsx` | modify | tests for those buttons |
| `README.md`, `docs/PROJECT_STATE.md` | modify | describe the launch rule |

---

### Task 1: Launch rule module

**Files:**
- Create: `frontend/src/app/launch.ts`
- Test: `frontend/src/app/launch.test.ts`

**Interfaces:**
- Produces:
  - `type LaunchDecision = 'deciding' | 'admin' | 'courier' | 'shop'`
  - `const LAUNCH_TIMEOUT_MS = 3000`
  - `startLaunch(openedAt: string): void`, `isLaunchPending(): boolean`, `finishLaunch(): void`
  - `decideLaunch(isAdmin: boolean | undefined, isCourier: boolean | undefined, timedOut: boolean): LaunchDecision` (`undefined` = that check has not answered yet)

- [ ] **Step 1: Write the failing test** — `frontend/src/app/launch.test.ts`

```ts
import { describe, expect, it } from 'vitest'

import { decideLaunch, finishLaunch, isLaunchPending, startLaunch } from './launch'

describe('decideLaunch', () => {
  it.each([
    // isAdmin, isCourier, timedOut, expected
    [true, undefined, false, 'admin'],
    [true, true, false, 'admin'],
    [undefined, true, false, 'deciding'],
    [false, undefined, false, 'deciding'],
    [false, true, false, 'courier'],
    [false, false, false, 'shop'],
    [undefined, undefined, true, 'shop'],
    [undefined, true, true, 'courier'],
    [false, undefined, true, 'shop'],
  ] as const)('admin=%s courier=%s timedOut=%s -> %s', (isAdmin, isCourier, timedOut, expected) => {
    expect(decideLaunch(isAdmin, isCourier, timedOut)).toBe(expected)
  })
})

describe('the once-per-load flag', () => {
  it('is pending only for an app opened at the bare root', () => {
    startLaunch('/')
    expect(isLaunchPending()).toBe(true)

    startLaunch('/orders/12')
    expect(isLaunchPending()).toBe(false)
  })

  it('stays finished once the launch is decided', () => {
    startLaunch('/')
    finishLaunch()
    expect(isLaunchPending()).toBe(false)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- src/app/launch.test.ts`
Expected: FAIL, `Failed to resolve import "./launch"`.

- [ ] **Step 3: Write the implementation** — `frontend/src/app/launch.ts`

```ts
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- src/app/launch.test.ts`
Expected: PASS, 11 tests.

- [ ] **Step 5: Commit**

```bash
git add src/app/launch.ts src/app/launch.test.ts
git commit -m "feat(frontend): role-based launch rule"
```

---

### Task 2: LaunchGate

**Files:**
- Create: `frontend/src/app/LaunchGate.tsx`, `frontend/src/app/LaunchGate.module.css`
- Test: `frontend/src/app/LaunchGate.test.tsx`

**Interfaces:**
- Consumes: `decideLaunch`, `finishLaunch`, `isLaunchPending`, `LAUNCH_TIMEOUT_MS`, `LaunchDecision` (Task 1); `useIsAdmin()` from `features/admin/entry.ts` (react-query result, `data: boolean`; throws on errors other than 401/403); `useCourierProfile()` from `features/courier/hooks.ts` (`data: CourierProfile | null`).
- Produces: `LaunchGate({ children, timeoutMs? }: { children: ReactNode; timeoutMs?: number })`. Renders `children` when the shop should show; the loading skeleton has `role="status"` and the accessible name `t('common.loading')` ("Loading…").

- [ ] **Step 1: Write the failing test** — `frontend/src/app/LaunchGate.test.tsx`

```tsx
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { delay, http, HttpResponse } from 'msw'
import { useNavigate } from 'react-router-dom'
import { beforeEach, describe, expect, it } from 'vitest'

import { adminMe } from '../test/adminFixtures'
import { courierProfile } from '../test/fixtures'
import { API } from '../test/mocks/handlers'
import { server } from '../test/mocks/server'
import { renderScreen } from '../test/test-utils'
import { startLaunch } from './launch'
import { LaunchGate } from './LaunchGate'

function BackToShop() {
  const navigate = useNavigate()
  return (
    <button type="button" onClick={() => navigate('/')}>
      to shop
    </button>
  )
}

function renderLaunch(timeoutMs?: number) {
  return renderScreen(
    <LaunchGate timeoutMs={timeoutMs}>
      <div>shop home</div>
    </LaunchGate>,
    {
      extraRoutes: [
        { path: '/admin', element: <div>admin page</div> },
        {
          path: '/courier',
          element: (
            <div>
              courier page <BackToShop />
            </div>
          ),
        },
      ],
    },
  )
}

function asAdmin() {
  server.use(http.get(`${API}/internal/me`, () => HttpResponse.json(adminMe('dispatcher'))))
}

function asCourier() {
  server.use(http.get(`${API}/courier/me`, () => HttpResponse.json(courierProfile)))
}

function failing(path: string) {
  server.use(http.get(`${API}${path}`, () => new HttpResponse(null, { status: 500 })))
}

const settle = () => new Promise((resolve) => setTimeout(resolve, 50))

beforeEach(() => startLaunch('/'))

describe('LaunchGate: opened at the root', () => {
  it('shows a customer the shop', async () => {
    renderLaunch()

    expect(await screen.findByText('shop home')).toBeInTheDocument()
  })

  it('sends a courier to the courier screen', async () => {
    asCourier()
    renderLaunch()

    expect(await screen.findByText('courier page')).toBeInTheDocument()
  })

  it('sends an admin to the admin panel', async () => {
    asAdmin()
    renderLaunch()

    expect(await screen.findByText('admin page')).toBeInTheDocument()
  })

  it('prefers the admin panel for someone who is both', async () => {
    asAdmin()
    asCourier()
    renderLaunch()

    expect(await screen.findByText('admin page')).toBeInTheDocument()
  })

  it('still sends a courier on when the admin check fails', async () => {
    failing('/internal/me')
    asCourier()
    renderLaunch()

    expect(await screen.findByText('courier page')).toBeInTheDocument()
  })

  it('shows the shop when both checks fail', async () => {
    failing('/internal/me')
    failing('/courier/me')
    renderLaunch()

    expect(await screen.findByText('shop home')).toBeInTheDocument()
  })

  it('shows a loading skeleton, not the shop, while checking', async () => {
    server.use(
      http.get(`${API}/internal/me`, async () => {
        await delay(100)
        return HttpResponse.json({ detail: 'Not an admin' }, { status: 403 })
      }),
    )
    renderLaunch()

    expect(screen.getByRole('status', { name: 'Loading…' })).toBeInTheDocument()
    expect(screen.queryByText('shop home')).not.toBeInTheDocument()
    expect(await screen.findByText('shop home')).toBeInTheDocument()
  })

  it('shows the shop after the timeout and ignores a late answer', async () => {
    server.use(
      http.get(`${API}/internal/me`, async () => {
        await delay(300)
        return HttpResponse.json(adminMe('owner'))
      }),
    )
    renderLaunch(50)

    expect(await screen.findByText('shop home')).toBeInTheDocument()
    await new Promise((resolve) => setTimeout(resolve, 400))
    expect(screen.getByText('shop home')).toBeInTheDocument()
    expect(screen.queryByText('admin page')).not.toBeInTheDocument()
  })

  it('lets a courier go back to the shop without bouncing', async () => {
    const user = userEvent.setup()
    asCourier()
    renderLaunch()

    await user.click(await screen.findByRole('button', { name: 'to shop' }))

    expect(await screen.findByText('shop home')).toBeInTheDocument()
    await settle()
    expect(screen.queryByText('courier page')).not.toBeInTheDocument()
  })
})

describe('LaunchGate: opened anywhere else', () => {
  it('never redirects, even for a courier', async () => {
    startLaunch('/orders/1')
    asCourier()
    renderLaunch()

    expect(screen.getByText('shop home')).toBeInTheDocument()
    await settle()
    expect(screen.queryByText('courier page')).not.toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- src/app/LaunchGate.test.tsx`
Expected: FAIL, `Failed to resolve import "./LaunchGate"`.

- [ ] **Step 3: Write the implementation**

`frontend/src/app/LaunchGate.module.css`:

```css
.skeleton {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-4);
  padding-top: calc(var(--space-4) + var(--safe-top));
}
```

`frontend/src/app/LaunchGate.tsx`:

```tsx
import { type ReactNode, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Navigate } from 'react-router-dom'

import { useIsAdmin } from '../features/admin/entry'
import { useCourierProfile } from '../features/courier/hooks'
import { Skeleton } from '../shared/ui/Skeleton'
import {
  decideLaunch,
  finishLaunch,
  isLaunchPending,
  LAUNCH_TIMEOUT_MS,
  type LaunchDecision,
} from './launch'
import styles from './LaunchGate.module.css'

interface LaunchGateProps {
  children: ReactNode
  /** How long the role checks may take before the shop is shown anyway. */
  timeoutMs?: number
}

/**
 * Wraps the shop. On a launch at `/` it holds the shop back until it knows the user's role,
 * then sends an admin to the panel and a courier to their screen (Spec 8 §4). The checks are
 * the same queries the shell uses for its icons, so the cache shares one request each.
 */
export function LaunchGate({ children, timeoutMs = LAUNCH_TIMEOUT_MS }: LaunchGateProps) {
  const { t } = useTranslation()
  const [decision, setDecision] = useState<LaunchDecision>(() =>
    isLaunchPending() ? 'deciding' : 'shop',
  )
  const [timedOut, setTimedOut] = useState(false)
  const adminQuery = useIsAdmin()
  const courierQuery = useCourierProfile()

  const deciding = decision === 'deciding'
  // A failed check is a plain "no": the shop still works, and the icons appear if it recovers.
  const isAdmin = adminQuery.isPending ? undefined : adminQuery.data === true
  const isCourier = courierQuery.isPending ? undefined : !!courierQuery.data
  const next = deciding ? decideLaunch(isAdmin, isCourier, timedOut) : decision

  useEffect(() => {
    if (!deciding) return
    const timer = setTimeout(() => setTimedOut(true), timeoutMs)
    return () => clearTimeout(timer)
  }, [deciding, timeoutMs])

  useEffect(() => {
    if (!deciding || next === 'deciding') return
    // Before navigating: coming back to `/` later must show the shop, not decide again.
    finishLaunch()
    setDecision(next)
  }, [deciding, next])

  if (decision === 'admin') return <Navigate to="/admin" replace />
  if (decision === 'courier') return <Navigate to="/courier" replace />
  if (decision === 'shop') return <>{children}</>
  return (
    <div className={styles.skeleton} role="status" aria-label={t('common.loading')}>
      <Skeleton height={40} radius="999px" />
      <Skeleton height={160} />
      <Skeleton height={160} />
    </div>
  )
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- src/app/LaunchGate.test.tsx`
Expected: PASS, 10 tests.

- [ ] **Step 5: Commit**

```bash
git add src/app/LaunchGate.tsx src/app/LaunchGate.module.css src/app/LaunchGate.test.tsx
git commit -m "feat(frontend): LaunchGate sends each role to its screen on launch"
```

---

### Task 3: Courier shell and the `nav.shop` string

**Files:**
- Create: `frontend/src/app/CourierShell.tsx`
- Test: `frontend/src/app/CourierShell.test.tsx`
- Modify: `frontend/src/shared/i18n/locales/en.json`, `ru.json`, `uz.json` (the top-level `nav` object)

**Interfaces:**
- Consumes: `useIsAdmin()` (`features/admin/entry.ts`); `IconButton` (`shared/ui/IconButton`, requires `aria-label`); styles `shell`, `topBar`, `spacer`, `content` from `app/AppShell.module.css`.
- Produces: `CourierShell()`, a layout element rendering `<Outlet />`; i18n key `nav.shop`.

- [ ] **Step 1: Write the failing test** — `frontend/src/app/CourierShell.test.tsx`

```tsx
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { adminMe } from '../test/adminFixtures'
import { API } from '../test/mocks/handlers'
import { server } from '../test/mocks/server'
import { renderScreen } from '../test/test-utils'
import { CourierShell } from './CourierShell'

const options = {
  route: '/courier',
  path: '/courier',
  extraRoutes: [
    { path: '/', element: <div>shop home</div> },
    { path: '/admin', element: <div>admin page</div> },
  ],
}

describe('CourierShell', () => {
  it('takes a courier to the shop', async () => {
    const user = userEvent.setup()
    renderScreen(<CourierShell />, options)

    await user.click(screen.getByRole('button', { name: 'Shop' }))

    expect(await screen.findByText('shop home')).toBeInTheDocument()
  })

  it('has no cart and no orders button', () => {
    renderScreen(<CourierShell />, options)

    expect(screen.queryByRole('button', { name: 'Cart' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'My orders' })).not.toBeInTheDocument()
  })

  it('hides the admin button from a courier who is not an admin', async () => {
    renderScreen(<CourierShell />, options)

    // Let the admin check settle before asserting that nothing appeared.
    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(screen.queryByRole('button', { name: 'Admin panel' })).not.toBeInTheDocument()
  })

  it('takes a courier who is also an admin to the panel', async () => {
    const user = userEvent.setup()
    server.use(http.get(`${API}/internal/me`, () => HttpResponse.json(adminMe('dispatcher'))))
    renderScreen(<CourierShell />, options)

    await user.click(await screen.findByRole('button', { name: 'Admin panel' }))

    expect(await screen.findByText('admin page')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- src/app/CourierShell.test.tsx`
Expected: FAIL, `Failed to resolve import "./CourierShell"`.

- [ ] **Step 3: Add the string** to the top-level `nav` object of each locale, after `"orders"`:

`en.json`:
```json
  "nav": {
    "catalog": "Catalog",
    "cart": "Cart",
    "orders": "Orders",
    "shop": "Shop"
  },
```

`ru.json`:
```json
  "nav": {
    "catalog": "Каталог",
    "cart": "Корзина",
    "orders": "Заказы",
    "shop": "Магазин"
  },
```

`uz.json`:
```json
  "nav": {
    "catalog": "Katalog",
    "cart": "Savat",
    "orders": "Buyurtmalar",
    "shop": "Do'kon"
  },
```

- [ ] **Step 4: Write the shell** — `frontend/src/app/CourierShell.tsx`

```tsx
import { Settings, Store } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Outlet, useNavigate } from 'react-router-dom'

import { useIsAdmin } from '../features/admin/entry'
import { IconButton } from '../shared/ui/IconButton'
import styles from './AppShell.module.css'

/**
 * The courier's own top bar (Spec 8 §5): a courier works here, so it offers the way back to
 * the shop instead of the shop's cart and orders.
 */
export function CourierShell() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const adminQuery = useIsAdmin()

  return (
    <div className={styles.shell}>
      <header className={styles.topBar}>
        <IconButton aria-label={t('nav.shop')} onClick={() => navigate('/')}>
          <Store size={18} />
        </IconButton>
        {/* Someone can be a courier and an admin; the panel is then one tap away. */}
        {adminQuery.data && (
          <IconButton aria-label={t('admin.open')} onClick={() => navigate('/admin')}>
            <Settings size={18} />
          </IconButton>
        )}
        <div className={styles.spacer} />
      </header>
      <main className={styles.content}>
        <Outlet />
      </main>
    </div>
  )
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `npm test -- src/app/CourierShell.test.tsx src/shared/i18n`
Expected: PASS (4 shell tests; the locale parity test still passes with the new key in all three files).

- [ ] **Step 6: Commit**

```bash
git add src/app/CourierShell.tsx src/app/CourierShell.test.tsx src/shared/i18n/locales
git commit -m "feat(frontend): courier shell with a way back to the shop"
```

---

### Task 4: Wire the gate and the courier shell into the app

**Files:**
- Modify: `frontend/src/app/router.tsx`
- Modify: `frontend/src/main.tsx`

**Interfaces:**
- Consumes: `LaunchGate` (Task 2), `CourierShell` (Task 3), `startLaunch` (Task 1).

- [ ] **Step 1: Replace `frontend/src/app/router.tsx`** with:

```tsx
import { createBrowserRouter, useParams } from 'react-router-dom'

import { CartScreen } from '../features/cart/screens/CartScreen'
import { CatalogHomeScreen } from '../features/catalog/screens/CatalogHomeScreen'
import { ProductDetailScreen } from '../features/catalog/screens/ProductDetailScreen'
import { CheckoutScreen } from '../features/checkout/screens/CheckoutScreen'
import { CourierScreen } from '../features/courier/screens/CourierScreen'
import { OrderDetailScreen } from '../features/orders/screens/OrderDetailScreen'
import { OrdersListScreen } from '../features/orders/screens/OrdersListScreen'
import { AppShell } from './AppShell'
import { CourierShell } from './CourierShell'
import { LaunchGate } from './LaunchGate'

function ProductDetailRoute() {
  // Remounts on navigation between products (same route element otherwise reuses local state).
  const { productId } = useParams<{ productId: string }>()
  return <ProductDetailScreen key={productId} />
}

export const router = createBrowserRouter([
  {
    // Its own shell, and its own chunk: shoppers never download the admin panel.
    path: '/admin/*',
    lazy: () =>
      import('../features/admin/AdminApp').then((module) => ({ Component: module.AdminApp })),
  },
  {
    // Its own shell too: a courier gets a way back to the shop, not the cart.
    path: '/courier',
    element: <CourierShell />,
    children: [{ index: true, element: <CourierScreen /> }],
  },
  {
    path: '/',
    // On a launch at `/`, sends admins and couriers to their screens first (Spec 8).
    element: (
      <LaunchGate>
        <AppShell />
      </LaunchGate>
    ),
    children: [
      { index: true, element: <CatalogHomeScreen /> },
      { path: 'products/:productId', element: <ProductDetailRoute /> },
      { path: 'cart', element: <CartScreen /> },
      { path: 'checkout', element: <CheckoutScreen /> },
      { path: 'orders', element: <OrdersListScreen /> },
      { path: 'orders/:orderId', element: <OrderDetailScreen /> },
    ],
  },
])
```

- [ ] **Step 2: In `frontend/src/main.tsx`**, import `startLaunch` and call it right after `initWebApp()`:

```tsx
import { AppProviders } from './app/providers'
import { startLaunch } from './app/launch'
import { router } from './app/router'
import { initWebApp } from './shared/telegram/webApp'

initWebApp()
// Telegram opens the bare root (initData rides in the hash); notification buttons open deeper
// paths, which must not be redirected.
startLaunch(window.location.pathname)
```

- [ ] **Step 3: Type-check, build and run the whole suite**

Run: `npm run build`
Expected: `tsc -b` and `vite build` succeed.

Run: `npm test`
Expected: all tests pass (the 348 from before plus those from Tasks 1–3). `CourierScreen.test.tsx` and `AppShell.test.tsx` mount their components directly, so the route move does not affect them.

- [ ] **Step 4: Smoke test in the dev server** (needs `VITE_DEV_MOCK_INIT_DATA` in `frontend/.env`, see README "Develop without Docker", and the local API; skip if the API is not running and rely on Task 6)

Run: `npm run dev`, open `http://localhost:5173/`.
Expected: a brief skeleton, then the screen for the mock user's role; `/courier` shows the Shop button and no cart.

- [ ] **Step 5: Commit**

```bash
git add src/app/router.tsx src/main.tsx
git commit -m "feat(frontend): route each role to its screen when the Mini App opens"
```

---

### Task 5: Shop and Courier buttons in the admin header

**Files:**
- Modify: `frontend/src/features/admin/components/AdminLayout.tsx`
- Test: `frontend/src/features/admin/AdminApp.test.tsx` (append a `describe`)

**Interfaces:**
- Consumes: `useCourierProfile()` (`features/courier/hooks.ts`); `IconButton`; `nav.shop` (Task 3), `courier.nav` (existing, "Courier").

- [ ] **Step 1: Write the failing test** — append to `frontend/src/features/admin/AdminApp.test.tsx` (it already imports `screen`, `userEvent`, `http`, `HttpResponse`, `describe`, `expect`, `it`, `API`, `stubAdminBackend`, `server`, `renderScreen`, `AdminApp`); add one import at the top:

```tsx
import { courierProfile } from '../../test/fixtures'
```

and at the end of the file:

```tsx
describe('AdminApp: switching to other screens', () => {
  const withOtherScreens = {
    route: '/admin',
    path: '/admin/*',
    extraRoutes: [
      { path: '/', element: <div>shop home</div> },
      { path: '/courier', element: <div>courier page</div> },
    ],
  }

  it('takes an admin to the shop', async () => {
    const user = userEvent.setup()
    stubAdminBackend('owner')
    renderScreen(<AdminApp />, withOtherScreens)

    await user.click(await screen.findByRole('button', { name: 'Shop' }))

    expect(await screen.findByText('shop home')).toBeInTheDocument()
  })

  it('hides the courier button from an admin who is not a courier', async () => {
    stubAdminBackend('owner')
    renderScreen(<AdminApp />, withOtherScreens)

    await screen.findByRole('button', { name: 'Shop' })
    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(screen.queryByRole('button', { name: 'Courier' })).not.toBeInTheDocument()
  })

  it('takes an admin who is also a courier to the courier screen', async () => {
    const user = userEvent.setup()
    stubAdminBackend('owner')
    server.use(http.get(`${API}/courier/me`, () => HttpResponse.json(courierProfile)))
    renderScreen(<AdminApp />, withOtherScreens)

    await user.click(await screen.findByRole('button', { name: 'Courier' }))

    expect(await screen.findByText('courier page')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- src/features/admin/AdminApp.test.tsx`
Expected: the three new tests FAIL (`Unable to find role="button" and name "Shop"`); the existing ones pass.

- [ ] **Step 3: Implement** in `AdminLayout.tsx`

Imports: add `Store` to the `lucide-react` import (alphabetical: after `Package`), change the router import to `import { NavLink, useNavigate } from 'react-router-dom'`, and add:

```tsx
import { IconButton } from '../../../shared/ui/IconButton'
import { useCourierProfile } from '../../courier/hooks'
```

In the component body, after `const logout = useLogout()`:

```tsx
  const navigate = useNavigate()
  const courierQuery = useCourierProfile()
```

In the header, between the `.who` block and the language `<select>`:

```tsx
          {/* Spec 8 §5: the way back to the shop; not in the nav, which is full on phones. */}
          <IconButton aria-label={t('nav.shop')} onClick={() => navigate('/')}>
            <Store size={18} aria-hidden />
          </IconButton>
          {courierQuery.data && (
            <IconButton aria-label={t('courier.nav')} onClick={() => navigate('/courier')}>
              <Truck size={18} aria-hidden />
            </IconButton>
          )}
```

(`/courier/me` without initData, i.e. in a desktop browser, answers 401: the query errors, `data` stays undefined and the button stays hidden. Its key is `['courier', 'profile']`, so the panel's session watch, which only reacts to `['admin', …]` keys, ignores it.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test -- src/features/admin`
Expected: PASS, including the three new tests.

- [ ] **Step 5: Commit**

```bash
git add src/features/admin/components/AdminLayout.tsx src/features/admin/AdminApp.test.tsx
git commit -m "feat(frontend): shop and courier buttons in the admin header"
```

---

### Task 6: Docs, full checks, deploy

**Files:**
- Modify: `README.md`, `docs/PROJECT_STATE.md`, `docs/superpowers/specs/2026-10-04-role-based-launch-design.md` (status line)

- [ ] **Step 1: README, "Couriers & tracking"**: replace the first sentence

> Couriers use the same Mini App: once a Telegram account is registered as a courier, a truck icon
> appears in the header.

with

> Couriers use the same Mini App: once a Telegram account is registered as a courier, opening the
> bot lands on the courier screen, whose top bar has a **Shop** button for shopping as a customer
> (the shop then shows a truck icon to come back).

and in "**3. The courier's day.**" replace `Open the truck icon →` with `Open the bot →`.

- [ ] **Step 2: README, "Admin panel"**: replace

> Admins who open the Mini App see a gear icon in the
> top bar;

with

> Admins who open the bot land in the panel, even if they are also
> couriers; its header has **Shop** (and **Courier** for couriers), and the shop shows a gear icon
> to come back;

- [ ] **Step 3: `docs/PROJECT_STATE.md`**: add a row to the spec table in §1, after Spec 7:

```markdown
| 8 Role-based launch | opening the bot sends admins to `/admin`, couriers to `/courier`, everyone else to the shop; Shop/Courier/Admin switch buttons; frontend only (`app/launch.ts`, `LaunchGate`, `CourierShell`). Stage A of the marketplace roadmap (B sellers, C multi-seller orders, D money) in the spec | **done**, committed |
```

and in §3 update the frontend test count to the number `npm test` printed in Step 4.

- [ ] **Step 4: Full checks**

Run: `npm run lint` → no new warnings (one pre-existing oxlint warning in `router.tsx` is known).
Run: `npx prettier --check .` → clean (run `npx prettier --write` on the touched files if not).
Run: `npm run build` → succeeds.
Run: `npm test` → all pass; note the count for Step 3.

- [ ] **Step 5: Set the spec status** to `**implemented (2026-10-04).**` and commit

```bash
git add ../README.md ../docs/PROJECT_STATE.md ../docs/superpowers/specs/2026-10-04-role-based-launch-design.md
git commit -m "docs: role-based launch in README and project state"
```

- [ ] **Step 6: Deploy (ask the owner first: it changes production)**

Run: `npm run deploy:pages`
Expected: wrangler prints the deployment URL; `https://ecosmetics-shop.pages.dev/` serves the new build.

- [ ] **Step 7: Manual check in Telegram (owner)**

1. Owner account (an admin): open the bot with the menu button **Shop** → admin panel. Header **Shop** → the shop; gear → back to the panel.
2. A courier account (add one in the panel's Couriers section if none): open the bot → courier screen, Shop button, no cart.
3. A plain account → the shop, as before.
4. A notification button (e.g. an order message) still opens its own screen.

- [ ] **Step 8: Push** to `origin main` once the owner has seen it work (the repository is public).
