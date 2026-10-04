import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'

import { Card } from '../../../shared/ui/Card'
import { EmptyState } from '../../../shared/ui/EmptyState'
import { PillButton } from '../../../shared/ui/PillButton'
import { QueryError } from '../../../shared/ui/QueryError'
import { Skeleton } from '../../../shared/ui/Skeleton'
import { isPrice } from '../components/catalog/validation'
import { inputClass } from '../components/inputClass'
import { ErrorNote, Field, PageHeader } from '../components/ui'
import { adminErrorKey } from '../errors'
import { formatDateTime, formatMoney, formatPercent } from '../format'
import { useAdminSellers, useMyEarnings, useRecordPayout, useSellerLedger } from '../hooks'
import type { Ledger } from '../types'
import detail from './OrderDetailScreen.module.css'

/** Balance, earnings by order and payouts: the same for the platform and the seller (Spec 11). */
function LedgerView({ ledger }: { ledger: Ledger }) {
  const { t, i18n } = useTranslation()
  const money = (amount: string, currency: string) => formatMoney(amount, currency, i18n.language)

  return (
    <>
      {ledger.balances.map((b) => (
        <Card key={b.currency} className={detail.card}>
          <dl className={detail.totals}>
            <dt>{t('admin.money.earned')}</dt>
            <dd>{money(b.earned, b.currency)}</dd>
            <dt>{t('admin.money.paidOut')}</dt>
            <dd>{money(b.paid_out, b.currency)}</dd>
            <dt className={detail.strong}>{t('admin.money.owed')}</dt>
            <dd className={detail.strong}>{money(b.balance, b.currency)}</dd>
          </dl>
        </Card>
      ))}

      <Card className={detail.card}>
        <h2 className={detail.cardTitle}>{t('admin.money.earnings')}</h2>
        {ledger.earnings.length === 0 ? (
          <p className={detail.muted}>{t('admin.money.nothingYet')}</p>
        ) : (
          <ul className={detail.items}>
            {ledger.earnings.map((e) => (
              <li key={e.order_id} className={detail.item}>
                <span className={detail.itemMain}>
                  <span>{t('admin.orders.number', { id: e.order_id })}</span>
                  <span className={detail.muted}>
                    {t('admin.money.earningLine', {
                      goods: money(e.goods_total, e.currency),
                      percent: formatPercent(e.commission_percent),
                      commission: money(e.commission, e.currency),
                    })}
                  </span>
                  <span className={detail.muted}>{formatDateTime(e.earned_at, i18n.language)}</span>
                </span>
                <span className={detail.strong}>{money(e.amount, e.currency)}</span>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card className={detail.card}>
        <h2 className={detail.cardTitle}>{t('admin.money.payouts')}</h2>
        {ledger.payouts.length === 0 ? (
          <p className={detail.muted}>{t('admin.money.noPayouts')}</p>
        ) : (
          <ul className={detail.items}>
            {ledger.payouts.map((p) => (
              <li key={p.id} className={detail.item}>
                <span className={detail.itemMain}>
                  <span>{formatDateTime(p.created_at, i18n.language)}</span>
                  {p.note && <span className={detail.muted}>{p.note}</span>}
                </span>
                <span className={detail.strong}>{money(p.amount, p.currency)}</span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </>
  )
}

function PayoutForm({ sellerId, currencies }: { sellerId: number; currencies: string[] }) {
  const { t } = useTranslation()
  const [form, setForm] = useState({ amount: '', currency: currencies[0] ?? 'UZS', note: '' })
  const [invalid, setInvalid] = useState<string | null>(null)
  const record = useRecordPayout(sellerId)

  function submit(event: FormEvent) {
    event.preventDefault()
    if (!isPrice(form.amount)) {
      setInvalid(t('admin.catalog.invalidPrice'))
      return
    }
    setInvalid(null)
    record.mutate(
      { amount: form.amount.trim(), currency: form.currency, note: form.note.trim() || null },
      { onSuccess: () => setForm({ ...form, amount: '', note: '' }) },
    )
  }

  return (
    <Card className={detail.card}>
      <form onSubmit={submit}>
        <h2 className={detail.cardTitle}>{t('admin.money.recordPayout')}</h2>
        <p className={detail.muted}>{t('admin.money.payoutHint')}</p>
        <Field label={t('admin.money.amount')}>
          {(id) => (
            <input
              id={id}
              required
              inputMode="decimal"
              className={inputClass}
              value={form.amount}
              onChange={(event) => setForm({ ...form, amount: event.target.value })}
            />
          )}
        </Field>
        {currencies.length > 1 && (
          <Field label={t('admin.money.currency')}>
            {(id) => (
              <select
                id={id}
                className={inputClass}
                value={form.currency}
                onChange={(event) => setForm({ ...form, currency: event.target.value })}
              >
                {currencies.map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </select>
            )}
          </Field>
        )}
        <Field label={t('admin.money.note')}>
          {(id) => (
            <input
              id={id}
              maxLength={500}
              className={inputClass}
              value={form.note}
              onChange={(event) => setForm({ ...form, note: event.target.value })}
            />
          )}
        </Field>
        <ErrorNote message={invalid ?? (record.error ? t(adminErrorKey(record.error)) : null)} />
        {record.isSuccess && (
          <p className={detail.muted} role="status">
            {t('admin.money.recorded')}
          </p>
        )}
        <div className={detail.actions}>
          <PillButton type="submit" disabled={record.isPending}>
            {t('admin.money.recordPayout')}
          </PillButton>
        </div>
      </form>
    </Card>
  )
}

/** The platform's view of one seller's money, with the payout form (`payouts.manage`). */
export function SellerLedgerScreen() {
  const { t } = useTranslation()
  const sellerId = Number(useParams<{ sellerId: string }>().sellerId)
  const query = useSellerLedger(sellerId)
  const sellers = useAdminSellers()
  const name = sellers.data?.find((s) => s.id === sellerId)?.name ?? ''

  if (query.isError && !query.data) return <QueryError onRetry={() => query.refetch()} />
  if (!query.data) return <Skeleton height={320} />

  return (
    <div className={detail.screen}>
      <Link to="/admin/sellers" className={detail.back}>
        ← {t('admin.nav.sellers')}
      </Link>
      <PageHeader title={name} />
      <PayoutForm sellerId={sellerId} currencies={query.data.balances.map((b) => b.currency)} />
      <LedgerView ledger={query.data} />
    </div>
  )
}

/** A seller's own money (Spec 11): nothing to record, only to read. */
export function SellerMoneyScreen() {
  const { t } = useTranslation()
  const query = useMyEarnings()

  if (query.isError && !query.data) return <QueryError onRetry={() => query.refetch()} />
  if (!query.data) return <Skeleton height={320} />

  return (
    <div className={detail.screen}>
      <PageHeader title={t('admin.nav.earnings')} />
      {query.data.balances.length === 0 && query.data.earnings.length === 0 ? (
        <EmptyState title={t('admin.money.nothingYet')} />
      ) : (
        <LedgerView ledger={query.data} />
      )}
    </div>
  )
}
