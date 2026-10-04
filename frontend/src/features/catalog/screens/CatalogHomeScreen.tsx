import { Search, X } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router-dom'

import { DEFAULT_CURRENCY } from '../../../shared/constants'
import { CategoryPills } from '../components/CategoryPills'
import { ProductGrid } from '../components/ProductGrid'
import { useCategories, useProducts } from '../hooks'
import styles from './CatalogHomeScreen.module.css'

export function CatalogHomeScreen() {
  const { t } = useTranslation()
  const [selectedCategoryId, setSelectedCategoryId] = useState<number | null>(null)
  const [query, setQuery] = useState('')

  // `?seller=` comes from a product page's seller link (Spec 9).
  const [searchParams, setSearchParams] = useSearchParams()
  const sellerParam = Number(searchParams.get('seller'))
  const sellerId = Number.isInteger(sellerParam) && sellerParam > 0 ? sellerParam : undefined

  const categoriesQuery = useCategories()
  const productsQuery = useProducts(selectedCategoryId ?? undefined, sellerId)
  const sellerName = productsQuery.data?.[0]?.seller.name

  const filteredProducts = useMemo(() => {
    const products = productsQuery.data ?? []
    if (!query.trim()) return products
    const needle = query.trim().toLowerCase()
    return products.filter((product) => product.name.toLowerCase().includes(needle))
  }, [productsQuery.data, query])

  return (
    <div className={styles.screen}>
      <div className={styles.searchBar}>
        <Search size={16} className={styles.searchIcon} />
        <input
          className={styles.searchInput}
          type="search"
          placeholder={t('catalog.searchPlaceholder')}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
      </div>

      {sellerId !== undefined && (
        <div className={styles.sellerChip}>
          <span>{t('catalog.sellerProducts', { name: sellerName ?? '…' })}</span>
          <button
            type="button"
            className={styles.clearSeller}
            aria-label={t('catalog.allSellers')}
            onClick={() => setSearchParams({}, { replace: true })}
          >
            <X size={14} aria-hidden />
          </button>
        </div>
      )}

      <CategoryPills
        categories={categoriesQuery.data ?? []}
        selectedId={selectedCategoryId}
        onSelect={setSelectedCategoryId}
        allLabel={t('catalog.all')}
      />

      <ProductGrid
        products={filteredProducts}
        currency={DEFAULT_CURRENCY}
        isLoading={productsQuery.isLoading}
        isError={productsQuery.isError}
        onRetry={() => productsQuery.refetch()}
      />
    </div>
  )
}
