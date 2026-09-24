import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { OrderStatusBadge } from '../../orders/components/OrderStatusBadge'
import type { OrderStatus } from '../../orders/types'
import { Card } from '../../../shared/ui/Card'
import { EmptyState } from '../../../shared/ui/EmptyState'
import { QueryError } from '../../../shared/ui/QueryError'
import { Skeleton } from '../../../shared/ui/Skeleton'
import { Badge, PageHeader } from '../components/ui'
import { formatMoney } from '../format'
import { useSummary } from '../hooks'
import type { StatsPeriod } from '../types'
import styles from './SummaryScreen.module.css'

const PERIODS: StatsPeriod[] = ['today', '7d', '30d']

export function SummaryScreen() {
  const { t, i18n } = useTranslation()
  const [period, setPeriod] = useState<StatsPeriod>('today')
  const query = useSummary(period)
  const summary = query.data

  return (
    <div className={styles.screen}>
      <PageHeader title={t('admin.nav.summary')} />
      <div role="tablist" aria-label={t('admin.summary.period')} className={styles.periods}>
        {PERIODS.map((p) => (
          <button
            key={p}
            type="button"
            role="tab"
            aria-selected={p === period}
            className={[styles.period, p === period ? styles.activePeriod : ''].join(' ')}
            onClick={() => setPeriod(p)}
          >
            {t(`admin.summary.periods.${p}`)}
          </button>
        ))}
      </div>

      {query.isError && !summary && <QueryError onRetry={() => query.refetch()} />}
      {!summary && query.isLoading && <Skeleton height={120} />}

      {summary && (
        <>
          <div className={styles.metrics}>
            <Card className={styles.metric}>
              <span className={styles.metricLabel}>{t('admin.summary.revenue')}</span>
              <span className={styles.metricValue}>
                {formatMoney(summary.revenue, summary.currency, i18n.language)}
              </span>
            </Card>
            <Card className={styles.metric}>
              <span className={styles.metricLabel}>{t('admin.summary.orders')}</span>
              <span className={styles.metricValue}>{summary.orders_count}</span>
            </Card>
            <Card className={styles.metric}>
              <span className={styles.metricLabel}>{t('admin.summary.average')}</span>
              <span className={styles.metricValue}>
                {formatMoney(summary.average_order, summary.currency, i18n.language)}
              </span>
            </Card>
          </div>

          <section className={styles.section}>
            <h2 className={styles.sectionTitle}>{t('admin.summary.byStatus')}</h2>
            <div className={styles.statuses}>
              {(Object.entries(summary.status_counts) as [OrderStatus, number][]).map(
                ([status, count]) => (
                  <Link
                    key={status}
                    to={`/admin/orders?status=${status}`}
                    className={styles.statusLink}
                  >
                    <OrderStatusBadge status={status} />
                    <span className={styles.count}>{count}</span>
                  </Link>
                ),
              )}
            </div>
          </section>

          <div className={styles.columns}>
            <section className={styles.section}>
              <h2 className={styles.sectionTitle}>{t('admin.summary.lowStock')}</h2>
              {summary.low_stock.length === 0 ? (
                <EmptyState title={t('admin.summary.lowStockEmpty')} />
              ) : (
                <ul className={styles.list}>
                  {summary.low_stock.map((item) => (
                    <li key={item.variant_id}>
                      <Link
                        to={`/admin/catalog/products/${item.product_id}`}
                        className={styles.row}
                      >
                        <span className={styles.rowMain}>
                          <span>{item.name}</span>
                          <span className={styles.muted}>{item.sku}</span>
                        </span>
                        <Badge tone={item.stock_qty <= 0 ? 'negative' : 'warning'}>
                          {t('admin.summary.left', { count: item.stock_qty })}
                        </Badge>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className={styles.section}>
              <h2 className={styles.sectionTitle}>{t('admin.summary.topProducts')}</h2>
              {summary.top_products.length === 0 ? (
                <EmptyState title={t('admin.summary.noSales')} />
              ) : (
                <ol className={styles.list}>
                  {summary.top_products.map((item) => (
                    <li key={item.product_id} className={styles.row}>
                      <span className={styles.rowMain}>
                        <span>{item.name}</span>
                        <span className={styles.muted}>
                          {formatMoney(item.revenue, summary.currency, i18n.language)}
                        </span>
                      </span>
                      <span className={styles.count}>
                        {t('admin.summary.sold', { count: item.qty })}
                      </span>
                    </li>
                  ))}
                </ol>
              )}
            </section>
          </div>
        </>
      )}
    </div>
  )
}
