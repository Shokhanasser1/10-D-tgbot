# Spec 7: Admin roles, permissions and password login

Status: **designed and approved by the owner (2026-09-29), not implemented.**

## 1. Problem

Admins can only sign in through Telegram: inside the Mini App (initData) or in a browser with the
Telegram Login Widget, which needs `/setdomain` and a stable public https domain, so it does not work
on localhost or on a changing tunnel address. There are no passwords. Roles are three (owner,
catalog manager, dispatcher), each route lists allowed roles, a dispatcher can cancel paid orders
and so refund money, and nothing guards money or admin management beyond the role itself: anyone
holding an owner's unlocked phone can refund orders and add admins.

## 2. Decisions (confirmed by the owner)

| Question | Decision |
|---|---|
| Roles | six: owner, **manager**, catalog manager, dispatcher, **accountant**, **viewer** (matrix §3) |
| Password login | yes, next to Telegram sign-in |
| How an admin gets a password | sets it in their **Profile** after signing in with Telegram; an **owner can reset** it (a temporary password shown once, must be changed on next sign-in); the first owner can set one from the terminal |
| Extra protection for dangerous actions (🔒) | **re-enter the password**, valid for 15 minutes |

## 3. Permissions

Routes check one permission each; one module maps roles to permissions.

| Permission | owner | manager | catalog_manager | dispatcher | accountant | viewer |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| `summary.view` | ✓ | ✓ | | | ✓ | ✓ |
| `catalog.view` | ✓ | ✓ | ✓ | | | ✓ |
| `catalog.edit` (incl. prices, stock, photos) | ✓ | ✓ | ✓ | | | |
| `orders.view` | ✓ | ✓ | | ✓ | ✓ | ✓ |
| `orders.cancel_unpaid` (no money taken: cash before delivery) | ✓ | ✓ | | ✓ | | |
| `orders.cancel_paid` 🔒 (money taken: refund follows) | ✓ | ✓ | | | ✓ | |
| `refunds.manage` 🔒 (retry refund, confirm manual refund) | ✓ | | | | ✓ | |
| `couriers.view` (list, deliveries, map) | ✓ | ✓ | | ✓ | | ✓ |
| `couriers.manage` (add, edit, deactivate, release a delivery) | ✓ | ✓ | | ✓ | | |
| `admins.manage` 🔒 (add, change role, deactivate, reset password) | ✓ | | | | | |

- 🔒 applies to **every** role, the owner included: that is the owner's extra protection.
- Cancel is one endpoint; the server decides which permission applies from the order's payment:
  a succeeded Stripe/Telegram payment needs `orders.cancel_paid` 🔒, anything else
  `orders.cancel_unpaid`.
- Viewing admins (`GET /internal/admins`) requires `admins.manage` (no 🔒 for reading).
- The internal token (`X-Internal-Token`, scripts) acts as an owner and skips 🔒.
- Notifications (Spec 5) about new orders go to owners, managers and dispatchers; refund problems to
  owners and accountants.
- `GET /internal/me` returns `permissions` (list), `has_password`, `must_change_password`, `login`;
  the admin UI shows sections and buttons from `permissions` only.

## 4. Password sign-in

Data (one migration, `admins`): `login` (unique, lower-case, nullable), `password_hash` (nullable),
`must_change_password` (bool), `session_version` (int, default 1), `failed_logins` (int),
`locked_until` (timestamptz, nullable), `password_changed_at` (timestamptz, nullable).

- Login: 3–32 of `a-z 0-9 _ . -`, stored lower-case, unique. Password: at least 10 characters and not
  equal to the login.
- Hash: `hashlib.scrypt` (n=2^14, r=8, p=1, 16-byte salt), stored as
  `scrypt$n$r$p$<salt b64>$<hash b64>`; verification with `hmac.compare_digest`. No new dependency.
- `POST /internal/auth/password {login, password}`: the existing per-IP limiter, then per account:
  5 wrong passwords in a row lock it for 15 minutes. Every failure (unknown login, wrong password,
  locked, inactive) answers the same 401 "Wrong login or password", so logins cannot be probed. A
  success resets `failed_logins` and sets the session cookie.
- Profile: `POST /internal/me/password {login?, current_password?, new_password}`. Setting the first
  password needs no current one (the admin is already signed in); changing an existing one needs it.
  Success bumps `session_version`, clears `must_change_password`, re-issues this browser's cookie.
- Owner reset: `POST /internal/admins/{id}/password-reset` (`admins.manage` 🔒) sets a random
  temporary password (shown once in the response), `must_change_password=true`, bumps
  `session_version`. Resetting one's own password is refused (use Profile).
- While `must_change_password` is set, every `/internal/*` call except `me`, `me/password`, and logout
  answers 403 `password_change_required`.
- Terminal: `python -m scripts.set_admin_password <telegram_id> [--login name]` asks for the password
  twice (hidden) and sets it for an existing admin row (e.g. the bootstrap owner) — for localhost and
  students.

## 5. Sessions and 🔒 confirmation

- Session cookie becomes `<telegram_id>.<session_version>.<issued_at>.<hmac>`; the version must match
  the admins row, so a password change or reset signs out every other session. Old 3-part cookies
  are invalid (one re-sign-in after the upgrade).
- `POST /internal/auth/confirm {password}` checks the password (same lockout counter) and sets a
  second signed cookie `admin_confirm` (`<telegram_id>.<session_version>.<confirmed_at>.<hmac>`,
  15 minutes, HttpOnly, SameSite=Strict, CSRF header required like other writes). Works in the browser
  and inside the Mini App (initData requests carry cookies too).
- 🔒 routes answer 403 `password_confirmation_required` without a valid confirmation, or
  403 `password_not_set` if the admin has no password yet. The UI then asks for the password (or
  sends the admin to Profile) and retries the action.

## 6. Frontend

- `/admin/login`: login + password form; the Telegram widget stays below it when configured.
- Profile screen (all admins): login, set/change password; forced when `must_change_password`.
- A shared confirm-password dialog: any admin action that fails with
  `password_confirmation_required` opens it, confirms, and retries once.
- Admins screen: the six roles with a one-line description each, "Reset password" with the
  temporary password shown once (copy button).
- Sections and buttons come from `me.permissions` (`permissions.ts` rewritten around permissions).
- en/ru/uz strings for everything.

## 7. Testing

Backend (TDD): the role → permission matrix (a parametrized test over every route and role);
cancel paid vs unpaid; 🔒 without/with/expired confirmation and for the owner; internal token skips
🔒; password rules; login success, wrong password, unknown login (same answer), lockout and unlock
after 15 minutes, inactive admin; profile set/change (current password required on change); reset by
owner, temporary password works once and forces a change; session version invalidation; CLI script;
migration round-trip; notification recipients per role.

Frontend: login form, profile set/change and forced change, confirm dialog retry, admin reset with the
one-time password, sections per permission for each role (viewer sees no edit buttons).

## 8. Out of scope

Two-factor codes, password recovery by e-mail/Telegram (an owner resets), per-product or per-category
permissions, custom roles edited in the UI, an audit log of admin actions.
