import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'

import { Card } from '../../../shared/ui/Card'
import { QueryError } from '../../../shared/ui/QueryError'
import { Skeleton } from '../../../shared/ui/Skeleton'
import { createProduct, updateProduct } from '../api'
import styles from '../components/catalog/catalog.module.css'
import { PhotosEditor } from '../components/catalog/PhotosEditor'
import { ProductBasicsForm } from '../components/catalog/ProductBasicsForm'
import { TranslationsEditor } from '../components/catalog/TranslationsEditor'
import { VariantsEditor } from '../components/catalog/VariantsEditor'
import { PageHeader } from '../components/ui'
import { adminErrorKey } from '../errors'
import {
  useAdminAttributes,
  useAdminCategories,
  useAdminProduct,
  useCatalogMutation,
} from '../hooks'
import type { ProductInput } from '../types'
import layout from './ProductEditorScreen.module.css'
import { EditGate } from '../components/EditGate'

function BackLink() {
  const { t } = useTranslation()
  return (
    <Link to="/admin/catalog" className={layout.back}>
      ← {t('admin.catalog.backToProducts')}
    </Link>
  )
}

function NewProduct() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const categories = useAdminCategories()
  const create = useCatalogMutation(createProduct)

  return (
    <div className={layout.screen}>
      <BackLink />
      <PageHeader title={t('admin.catalog.newProduct')} />
      <Card>
        {categories.data ? (
          <ProductBasicsForm
            categories={categories.data}
            submitLabel={t('admin.catalog.createAndContinue')}
            busy={create.isPending}
            error={create.error ? t(adminErrorKey(create.error)) : null}
            onSubmit={(input) =>
              create.mutate(input, {
                onSuccess: (product) =>
                  navigate(`/admin/catalog/products/${product.id}`, { replace: true }),
              })
            }
          />
        ) : (
          <Skeleton height={160} />
        )}
      </Card>
      {categories.data?.length === 0 && (
        <p className={styles.muted}>{t('admin.catalog.needCategoryFirst')}</p>
      )}
    </div>
  )
}

function ExistingProduct({ productId }: { productId: number }) {
  const { t } = useTranslation()
  const productQuery = useAdminProduct(productId)
  const categories = useAdminCategories()
  const attributes = useAdminAttributes()
  const update = useCatalogMutation((input: ProductInput) => updateProduct(productId, input))

  const product = productQuery.data
  if (productQuery.isError && !product) return <QueryError onRetry={() => productQuery.refetch()} />
  if (!product || !categories.data || !attributes.data) {
    return (
      <div className={layout.screen}>
        <Skeleton height={320} />
      </div>
    )
  }

  const categoryAttributes = attributes.data.filter((a) => a.category_id === product.category_id)

  return (
    <div className={layout.screen}>
      <BackLink />
      <PageHeader title={product.name} />

      <Card className={styles.section}>
        <h2 className={styles.sectionTitle}>{t('admin.catalog.basics')}</h2>
        <ProductBasicsForm
          initial={product}
          categories={categories.data}
          submitLabel={t('admin.common.save')}
          busy={update.isPending}
          error={update.error ? t(adminErrorKey(update.error)) : null}
          onSubmit={(input) => update.mutate(input)}
        />
      </Card>

      <Card className={styles.section}>
        <h2 className={styles.sectionTitle}>{t('admin.catalog.texts')}</h2>
        <TranslationsEditor
          entityType="product"
          entityId={product.id}
          translations={product.translations}
          fields={[
            { key: 'name', label: t('admin.catalog.name') },
            { key: 'description', label: t('admin.catalog.description'), multiline: true },
          ]}
        />
      </Card>

      <Card className={styles.section}>
        <h2 className={styles.sectionTitle}>{t('admin.catalog.variants')}</h2>
        <VariantsEditor
          productId={product.id}
          variants={product.variants}
          attributes={categoryAttributes}
          defaultPrice={product.base_price}
        />
      </Card>

      <Card className={styles.section}>
        <h2 className={styles.sectionTitle}>{t('admin.catalog.photos')}</h2>
        <PhotosEditor productId={product.id} images={product.images} variants={product.variants} />
      </Card>
    </div>
  )
}

export function ProductEditorScreen({ productId }: { productId: number | null }) {
  return (
    <EditGate permission="catalog.edit">
      {productId === null ? <NewProduct /> : <ExistingProduct productId={productId} />}
    </EditGate>
  )
}
