import { useDeferredValue, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { DEFAULT_CURRENCY } from '../../../shared/constants'
import { EmptyState } from '../../../shared/ui/EmptyState'
import { PillButton } from '../../../shared/ui/PillButton'
import { useCan } from '../meContext'
import { QueryError } from '../../../shared/ui/QueryError'
import { Skeleton } from '../../../shared/ui/Skeleton'
import { PRODUCTS_PAGE_SIZE } from '../api'
import { ProductStatusBadge } from '../components/catalog/ProductStatusBadge'
import { Badge, PageHeader } from '../components/ui'
import { formatMoney } from '../format'
import { useAdminCategories, useAdminProducts } from '../hooks'
import type { ProductStatus } from '../types'
import { inputClass } from '../components/inputClass'
import styles from './ProductsScreen.module.css'

const STATUSES: ProductStatus[] = ['active', 'draft', 'archived']

export function ProductsScreen() {
  const { t, i18n } = useTranslation()
  const [q, setQ] = useState('')
  const [status, setStatus] = useState<ProductStatus | ''>('')
  const [categoryId, setCategoryId] = useState('')
  const [offset, setOffset] = useState(0)
  const deferredQ = useDeferredValue(q)

  const categories = useAdminCategories()
  const canEdit = useCan('catalog.edit')
  const query = useAdminProducts({
    q: deferredQ.trim() || undefined,
    status: status || undefined,
    category_id: categoryId ? Number(categoryId) : undefined,
    offset,
  })
  const page = query.data
  const categoryName = new Map(categories.data?.map((c) => [c.id, c.name]))

  function resetting<T>(setter: (value: T) => void) {
    return (value: T) => {
      setter(value)
      setOffset(0)
    }
  }

  return (
    <div className={styles.screen}>
      <PageHeader
        title={t('admin.nav.catalog')}
        actions={
          <>
            <Link to="/admin/catalog/categories" className={styles.secondaryLink}>
              {t('admin.catalog.categoriesAndAttributes')}
            </Link>
            {canEdit && (
              <Link to="/admin/catalog/new" className={styles.primaryLink}>
                {t('admin.catalog.addProduct')}
              </Link>
            )}
          </>
        }
      />

      <div className={styles.filters}>
        <input
          type="search"
          className={inputClass}
          placeholder={t('admin.catalog.search')}
          aria-label={t('admin.catalog.search')}
          value={q}
          onChange={(event) => resetting(setQ)(event.target.value)}
        />
        <select
          className={inputClass}
          aria-label={t('admin.catalog.status')}
          value={status}
          onChange={(event) => resetting(setStatus)(event.target.value as ProductStatus | '')}
        >
          <option value="">{t('admin.catalog.allStatuses')}</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {t(`admin.catalog.statuses.${s}`)}
            </option>
          ))}
        </select>
        <select
          className={inputClass}
          aria-label={t('admin.catalog.category')}
          value={categoryId}
          onChange={(event) => resetting(setCategoryId)(event.target.value)}
        >
          <option value="">{t('admin.catalog.allCategories')}</option>
          {categories.data?.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </div>

      {query.isError && !page && <QueryError onRetry={() => query.refetch()} />}
      {query.isLoading && <Skeleton height={200} />}
      {page && page.items.length === 0 && <EmptyState title={t('admin.catalog.empty')} />}

      {page && page.items.length > 0 && (
        <ul className={styles.list}>
          {page.items.map((product) => (
            <li key={product.id}>
              <Link to={`/admin/catalog/products/${product.id}`} className={styles.row}>
                {product.thumbnail_url ? (
                  <img src={product.thumbnail_url} alt="" className={styles.thumb} />
                ) : (
                  <span className={styles.thumb} aria-hidden />
                )}
                <span className={styles.main}>
                  <span className={styles.name}>{product.name}</span>
                  <span className={styles.muted}>
                    {product.base_sku} · {categoryName.get(product.category_id) ?? '—'}
                  </span>
                </span>
                <span className={styles.meta}>
                  <span>
                    {formatMoney(
                      product.min_price ?? product.base_price,
                      DEFAULT_CURRENCY,
                      i18n.language,
                    )}
                  </span>
                  <Badge tone={product.total_stock <= 0 ? 'negative' : 'neutral'}>
                    {t('admin.catalog.inStock', { count: product.total_stock })}
                  </Badge>
                </span>
                <ProductStatusBadge status={product.status} />
              </Link>
            </li>
          ))}
        </ul>
      )}

      {page && page.total > PRODUCTS_PAGE_SIZE && (
        <div className={styles.pager}>
          <PillButton
            variant="secondary"
            disabled={offset === 0}
            onClick={() => setOffset(Math.max(0, offset - PRODUCTS_PAGE_SIZE))}
          >
            {t('admin.common.previous')}
          </PillButton>
          <span className={styles.muted}>
            {t('admin.common.range', {
              from: offset + 1,
              to: Math.min(offset + PRODUCTS_PAGE_SIZE, page.total),
              total: page.total,
            })}
          </span>
          <PillButton
            variant="secondary"
            disabled={offset + PRODUCTS_PAGE_SIZE >= page.total}
            onClick={() => setOffset(offset + PRODUCTS_PAGE_SIZE)}
          >
            {t('admin.common.next')}
          </PillButton>
        </div>
      )}
    </div>
  )
}
