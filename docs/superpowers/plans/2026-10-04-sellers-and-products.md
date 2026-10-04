# Sellers and Products Implementation Plan

> **For agentic workers:** implement task by task, in order; each task ends green and committed.
> This plan is condensed: it fixes files, interfaces and the exact test cases, and the code is
> written test-first during execution (the executor is the plan's author). Steps use checkbox
> (`- [ ]`) syntax for tracking.

**Goal:** every product has a seller; a seller (a new admin role) manages only their own
products; customers see the seller; a cart holds one seller's products (Spec 9).

**Architecture:** a `sellers` table referenced by `products.seller_id` and `admins.seller_id`.
`AdminPrincipal.seller_id` carries the scope; `app/services/seller_scope.py` is the only place
that turns it into 404s and filters for the catalog routes. New permissions `taxonomy.edit` and
`sellers.manage`. The frontend reuses the admin panel: a Sellers section, seller select/filter in
the catalog, and on the storefront a seller label, filter and the cart confirmation.

**Tech Stack:** FastAPI, SQLAlchemy 2 async, Alembic, Postgres 16, pytest + httpx; React 19,
react-query v5, react-i18next, Vitest + MSW.

Spec: `docs/superpowers/specs/2026-10-04-sellers-and-products-design.md`.

## Global Constraints

- Backend tests need Postgres at `TEST_DATABASE_URL` (the compose `db` container on
  127.0.0.1:5432). Run from `backend/`: `python -m pytest -q`, lint `python -m ruff check app tests scripts`
  and `python -m ruff format --check app tests scripts` (line length 100).
- Frontend from `frontend/`: `npm test`, `npm run lint`, `npm run build`, prettier on touched files.
- Another seller's product/variant/image/translation → **404**, never 403. Category/attribute
  writes without `taxonomy.edit` → 403. Error codes: `cart_other_seller` (409),
  `seller_role_fixed` (409), `seller_inactive` (403), `already_exists` (409).
- Every new user-facing string in en/ru/uz.
- Commits: `<type>(backend|frontend): …` with the session's `Co-Authored-By` trailer.

---

### Task 1: Seller model, migration, test factories

**Files:** create `backend/app/models/seller.py`, `backend/alembic/versions/a9b8c7d6e5f4_sellers.py`;
modify `app/models/{__init__,product,admin,enums}.py`, `tests/factories.py` (or
`tests/seller_factories.py`), `tests/admin_factories.py`, every test that builds a `Product`
(`courier_factories`, `test_cart`, `test_catalog`, `test_catalog_admin_reads`, `test_checkout`,
`test_courier_concurrency`, `test_models`, `test_orders`, `test_payment_methods`,
`test_product_images`, `test_reservation`, `test_stock`, …), `scripts/seed_demo_data.py`,
`scripts/seed_courier_demo.py`, `tests/test_migrations.py`.

**Interfaces (produced):**
- `class Seller(TimestampMixin, Base)`: `id, name, phone, pickup_address, is_active`.
- `Product.seller_id: Mapped[int]`, `Product.seller: Mapped[Seller]`.
- `Admin.seller_id: Mapped[int | None]`, check `ck_admins_seller_role`.
- `AdminRole.seller`.
- `tests/factories.py`: `async def add_seller(db, name="Test shop", *, is_active=True, pickup_address="Tashkent, Amir Temur 1") -> Seller`
  and `async def default_seller_id(db) -> int` (one shared "Test shop" per test transaction).
- `tests/admin_factories.add_admin(..., seller_id: int | None = None)`: for `role=seller` without
  a `seller_id` it creates a seller.

**Tests:**
- `test_models`: a product without `seller_id` fails with IntegrityError; the role/seller check
  rejects `role=seller` without a seller and a non-seller role with one.
- `test_migrations`: upgrade from `f1a2b3c4d5e6` with two existing products → one seller
  `Main shop`, both products point at it; with no products → no seller row; downgrade deletes
  `role='seller'` admins and drops the columns; the existing "migrations match models" test passes.
- The whole existing suite passes after the factory updates.

- [ ] write the failing model tests → implement model + enum → migration → factories and the
  product-building tests → seeds (`seed_demo_data` creates seller "Demo shop") → full suite → commit
  `feat(backend): sellers table; every product belongs to a seller`.

---

### Task 2: Permissions, principal scope, `/internal/me`

**Files:** modify `app/models/enums.py` (`Permission.taxonomy_edit = "taxonomy.edit"`,
`Permission.sellers_manage = "sellers.manage"`), `app/core/permissions.py`, `app/api/deps.py`,
`app/services/admin_service.py`, `app/schemas/admin.py`, `app/api/routes/internal_auth.py`,
`app/api/routes/internal_products.py` (category/attribute writes need `taxonomy.edit`);
tests `test_admin_permissions.py`, `test_admin_auth.py`.

**Interfaces:**
- `ROLE_PERMISSIONS`: owner all; manager all − {refunds.manage, admins.manage} (so it has
  taxonomy.edit and sellers.manage); catalog_manager {catalog.view, catalog.edit, taxonomy.edit};
  seller {catalog.view, catalog.edit}; others unchanged.
- `AdminPrincipal.seller_id: int | None = None`.
- `admin_service.get_active_admin` keeps its signature; `_resolve_admin` (and the Login
  Widget/password sign-in) refuse an account whose seller is inactive:
  `ForbiddenError("This seller is deactivated", code="seller_inactive")`.
- `AdminMeOut.seller_id: int | None = None`, `AdminMeOut.seller_name: str | None = None`.

**Tests:** matrix gains `POST /internal/attributes`-style `taxonomy.edit` row (categories POST
moves from `catalog.edit` to `taxonomy.edit`) and covers `AdminRole.seller`; `/internal/me` of a
seller has `seller_id`/`seller_name`; a deactivated seller's account gets 403 `seller_inactive`
on `/internal/me` and on password sign-in.

- [ ] tests → implement → commit `feat(backend): seller role, taxonomy and sellers permissions`.

---

### Task 3: Seller scope on the catalog routes

**Files:** create `app/services/seller_scope.py`; modify `app/api/routes/internal_products.py`,
`app/services/catalog_admin_service.py` (create/update product take the resolved `seller_id`),
`app/services/catalog_admin_query_service.py` (`seller_id` filter; list items and detail return
`seller_id` and `seller_name`), `app/schemas/internal.py` (`ProductCreate.seller_id: int | None`,
`ProductUpdate.seller_id: int | None`, out schemas gain `seller_id`, `seller_name`);
test `tests/test_seller_scope.py`.

**Interfaces (`seller_scope`):**
- `async def product_in_scope(db, principal, product_id) -> None` (404 `Product not found`)
- `async def variant_in_scope(db, principal, variant_id) -> None` (404 `Variant not found`)
- `async def image_in_scope(db, principal, image_id) -> None` (404 `Image not found`)
- `async def translation_in_scope(db, principal, entity_type, entity_id) -> None`
  (403 for non-`product` types for a seller; 404 for another seller's product)
- `async def seller_for_new_product(db, principal, requested: int | None) -> int`
  (seller: own id, 404 if another is named; staff: required (400), must exist (404))
- `def list_filter(principal, requested: int | None) -> int | None`
- `def check_seller_change(principal, data: ProductUpdate) -> None` (403 for a seller)

All are no-ops for platform staff except where noted.

**Tests (`test_seller_scope.py`, two sellers A and B, a seller account of A):** list shows only
A's; `?seller_id=B` still only A's; GET/PATCH B's product 404; POST variant for B's product 404;
PATCH B's variant 404; POST image (JSON url) to B's product 404; PATCH/DELETE B's image 404;
POST translation for B's product 404, for a category 403; POST category/attribute 403; POST
product → seller A even when `seller_id` omitted, 404 with `seller_id=B`; PATCH own product with
`seller_id` 403; staff: POST product without `seller_id` 400, with it 201; `?seller_id=` filters;
list/detail carry `seller_name`.

- [ ] tests → implement → commit `feat(backend): sellers only reach their own products`.

---

### Task 4: Sellers API; the admins API refuses the seller role

**Files:** create `app/schemas/seller.py`, `app/services/seller_service.py`,
`app/api/routes/internal_sellers.py` (registered in `app/main.py`); modify
`app/services/admin_service.py`, `app/schemas/admin.py`; tests `tests/test_sellers_admin.py`,
`tests/test_admins_admin.py`.

**Interfaces:** `SellerCreate{name 1..100, phone? ≤32, pickup_address 1..500, telegram_id>0, display_name 1..100}`,
`SellerUpdate{name?, phone?, pickup_address?, is_active?}`,
`SellerOut{id, name, phone, pickup_address, is_active, accounts: list[SellerAccountOut], product_count}`;
`seller_service.list_sellers(db, only_id: int | None)`, `create_seller(db, data, created_by)`,
`update_seller(db, seller_id, data)`.

**Tests:** owner/manager create → seller + `role=seller` admin linked; catalog_manager/seller
POST 403; GET allowed for catalog_manager, a seller sees only itself; duplicate Telegram ID 409
`already_exists` and nothing written; PATCH name/address/is_active; deactivate → storefront
hides products (Task 5 asserts) and account gets `seller_inactive`; `POST /internal/admins`
role seller 409 `seller_role_fixed`; PATCH role to/from seller 409; PATCH `is_active` of a seller
account works.

- [ ] tests → implement → commit `feat(backend): owners manage sellers`.

---

### Task 5: Storefront catalog shows and filters by seller

**Files:** `app/schemas/catalog.py` (`SellerBrief{id, name}`; `seller` on list item and detail),
`app/services/catalog_service.py`, `app/api/routes/catalog.py` (`seller` query param); tests in
`tests/test_catalog.py`.

**Tests:** list and detail carry `seller`; `?seller=` filters; a deactivated seller's products
are not listed and detail is 404.

- [ ] tests → implement → commit `feat(backend): storefront shows each product's seller`.

---

### Task 6: One seller per cart

**Files:** `app/schemas/cart.py` (`CartItemIn.replace_cart: bool = False`, `CartOut.seller: SellerBrief | None`),
`app/services/cart_service.py`, `app/api/routes/cart.py`; tests in `tests/test_cart.py`,
`tests/test_reservation.py`.

**Behaviour:** `_get_active_variant` also requires an active seller. `add_item(db, telegram_id,
variant_id, qty, replace_cart=False)`: if the cart has lines of another seller → with
`replace_cart` delete them first, else `ConflictError("The cart holds another seller's products",
code="cart_other_seller")`. `restore_order_items` restores only into an empty cart or one of the
same seller.

**Tests:** 409 `cart_other_seller` and the cart unchanged; `replace_cart` leaves only the new
line; same seller adds normally; `GET /cart/items` has `seller` (null when empty); a deactivated
seller's variant → 404; expiry restore into another seller's cart drops the items and keeps the
cart.

- [ ] tests → implement → commit `feat(backend): a cart holds one seller's products`.

---

### Task 7: Admin panel: Sellers section, seller in the catalog

**Files:** `frontend/src/features/admin/{types,api,hooks,permissions}.ts`,
`components/AdminLayout.tsx` (+ css: ellipsis labels; seller name in header),
create `screens/SellersScreen.tsx` (+ `.module.css`, `.test.tsx`), `AdminApp.tsx` (route),
`screens/ProductsScreen.tsx` (seller column/label + staff filter),
`screens/ProductEditorScreen.tsx` / `components/catalog/ProductBasicsForm.tsx` (seller select for
staff), `screens/CategoriesScreen.tsx` (`taxonomy.edit`), `screens/AdminsScreen.tsx` (no seller
in the select, seller accounts as text), test mocks `src/test/mocks/adminBackend.ts`,
`src/test/adminFixtures.ts`, locales.

**Interfaces:** `AdminRole` + `'seller'`; `Permission` + `'taxonomy.edit' | 'sellers.manage'`;
`AdminMe.seller_id: number | null`, `AdminMe.seller_name: string | null`;
`AdminSeller`, `SellerInput`; `fetchSellers`, `createSeller`, `updateSeller`; `useAdminSellers()`;
section `'sellers'` after `'couriers'`.

**Tests:** Sellers screen lists, creates (body sent), deactivates; owner nav includes Sellers,
seller nav is Catalog + Profile; seller header shows the shop name; products list shows seller;
staff see the seller filter and the new-product seller select, a seller sees neither and the
create request has no `seller_id`; Categories read-only without `taxonomy.edit`; Admins screen
offers no seller role and renders a seller account as text.

- [ ] tests → implement → commit `feat(frontend): sellers in the admin panel`.

---

### Task 8: Storefront: seller label, filter, cart confirmation

**Files:** `frontend/src/features/catalog/{types,api,hooks}.ts`, `components/ProductCard.tsx`,
`screens/ProductDetailScreen.tsx`, `screens/CatalogHomeScreen.tsx`, `features/cart/{api,hooks,types}.ts`,
`shared/telegram/webApp.ts` (`confirmDialog(message): Promise<boolean>`), test fixtures/handlers,
locales.

**Tests:** card shows seller; product page shows seller and its tap opens `/?seller=ID`; home
with `?seller=` requests `seller=` and shows a chip that clears it; adding another seller's
product → confirm → second POST has `replace_cart: true` → navigates to cart; declining sends
nothing more.

- [ ] tests → implement → commit `feat(frontend): customers see sellers; one seller per cart`.

---

### Task 9: Docs and checks

- [ ] README ("Admin panel": sellers; a new "Sellers" paragraph), `docs/PROJECT_STATE.md`
  (Spec 9 row, test counts, alembic head, data model notes), spec status → implemented.
- [ ] backend: pytest, ruff check, ruff format --check; frontend: test, lint, build, prettier.
- [ ] commit `docs: sellers in README and project state`. Deploy and push wait for the owner
  (backend: JustRunMy subtree push; frontend: `deploy:pages`).
