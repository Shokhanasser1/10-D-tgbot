# Sellers' Money Implementation Plan

> **For agentic workers:** implement task by task, in order; each task ends green and committed.
> Condensed like the Spec 9 and 10 plans: files, interfaces and test cases are fixed here, the
> code is written test-first during execution.

**Goal:** per-seller commission, an earning per delivered order, recorded payouts and balances,
visible to the platform (Sellers) and to each seller (Money).

Spec: `docs/superpowers/specs/2026-10-04-seller-money-design.md`.

## Global Constraints

As in the Spec 9/10 plans. Money in `Decimal`, rounded half-up to cents. Writes of payouts need
`payouts.manage` and the 🔒 password confirmation (`CONFIRMATION_REQUIRED`).

### Task 1: data, checkout rate, earning on delivery
Models `Seller.commission_percent`, `Order.commission_percent`, `SellerEarning`, `SellerPayout`;
migration `c2d3e4f5a6b7_seller_money.py`; `checkout_service` copies the rate;
`app/services/earnings_service.py` (`record_earning(db, order_id)`, `commission_of(total, pct)`);
`dispatch_service` calls it on deliver; factories set `commission_percent` on orders built directly.
Tests: rate copied at checkout; deliver creates one earning (10% of 30.00 → 3.00 / 27.00; 12.5%
of 10.01 → 1.25 / 8.76); a second deliver call adds none; cash order too; migration fills rates.

### Task 2: payouts, balances, ledger, permissions
`Permission.payouts_manage` (owner, accountant; in `CONFIRMATION_REQUIRED`), `app/schemas/payouts.py`,
`earnings_service.balances/ledger/record_payout`, routes in `internal_sellers.py`
(`GET /sellers/{id}/ledger`, `POST /sellers/{id}/payouts`), seller list carries
`commission_percent` and `balances`, create/update accept the rate, `GET /internal/seller/earnings`,
notification `payout_recorded`.
Tests: balances per currency; payout ok (confirmed), without confirmation 403, above balance 409
`exceeds_balance`, ≤ 0 → 422, unknown seller 404, other roles 403; ledger order; the seller's own
earnings only and staff 403; the seller is notified; rate validation 0..100.

### Task 3: frontend
Types/api/hooks; Sellers form rate field; list "Owed"; `SellerLedgerScreen` at
`/admin/sellers/:sellerId` with the payout form through `withConfirmation`; section `sellers`
opens with `payouts.manage` too; seller section `earnings` ("Money") with `SellerMoneyScreen`;
strings; tests.

### Task 4: docs and checks
README, PROJECT_STATE, spec status, full checks, commit.
