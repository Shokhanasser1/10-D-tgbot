import { useCallback, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'

import { DEFAULT_CURRENCY } from '../../../shared/constants'
import { useMainButton } from '../../../shared/telegram/hooks'
import { confirmDialog } from '../../../shared/telegram/webApp'
import { ActionBar } from '../../../shared/ui/ActionBar'
import { Price } from '../../../shared/ui/Price'
import { QueryError } from '../../../shared/ui/QueryError'
import { Skeleton } from '../../../shared/ui/Skeleton'
import { isOtherSellerConflict } from '../../cart/api'
import { useAddCartItem, useCart } from '../../cart/hooks'
import { ImageCarousel } from '../components/ImageCarousel'
import { VariantPicker } from '../components/VariantPicker'
import { useProduct } from '../hooks'
import styles from './ProductDetailScreen.module.css'

export function ProductDetailScreen() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { productId } = useParams<{ productId: string }>()
  const id = Number(productId)

  const productQuery = useProduct(id)
  const addCartItem = useAddCartItem()
  const cartQuery = useCart()

  const [pickedVariantId, setPickedVariantId] = useState<number | null>(null)
  const selectedVariantId = pickedVariantId ?? productQuery.data?.variants[0]?.id ?? null

  const selectedVariant = useMemo(
    () => productQuery.data?.variants.find((variant) => variant.id === selectedVariantId),
    [productQuery.data, selectedVariantId],
  )

  const handleAddToCart = useCallback(() => {
    if (!selectedVariant) return
    const variantId = selectedVariant.id
    const toCart = { onSuccess: () => navigate('/cart') }
    addCartItem.mutate(
      { variantId, qty: 1 },
      {
        ...toCart,
        // A cart holds one seller's products (Spec 9): offer to start it over with this one.
        onError: async (error) => {
          if (!isOtherSellerConflict(error)) return
          const name = cartQuery.data?.seller?.name ?? ''
          if (await confirmDialog(t('cart.otherSeller', { name }))) {
            addCartItem.mutate({ variantId, qty: 1, replaceCart: true }, toCart)
          }
        },
      },
    )
  }, [selectedVariant, addCartItem, navigate, cartQuery.data, t])

  const outOfStock = !selectedVariant || selectedVariant.stock_qty <= 0
  const buttonLabel = outOfStock ? t('product.outOfStock') : t('product.addToCart')

  useMainButton({
    text: buttonLabel,
    onClick: handleAddToCart,
    visible: !!productQuery.data,
    enabled: !outOfStock && !addCartItem.isPending,
  })

  if (productQuery.isError) {
    return <QueryError onRetry={() => productQuery.refetch()} />
  }

  if (productQuery.isLoading || !productQuery.data) {
    return (
      <div className={styles.screen}>
        <Skeleton height={320} radius="18px" />
        <Skeleton height={20} width="60%" />
        <Skeleton height={16} width="40%" />
      </div>
    )
  }

  const product = productQuery.data
  const images = selectedVariant?.image_urls.length
    ? selectedVariant.image_urls
    : product.image_urls

  return (
    <div className={styles.screen}>
      <ImageCarousel images={images} alt={product.name} />

      <div className={styles.info}>
        <h1 className={styles.name}>{product.name}</h1>
        <button
          type="button"
          className={styles.seller}
          onClick={() => navigate(`/?seller=${product.seller.id}`)}
        >
          {t('product.seller', { name: product.seller.name })}
        </button>
        <Price amount={selectedVariant?.price ?? product.base_price} currency={DEFAULT_CURRENCY} />
      </div>

      {product.description && <p className={styles.description}>{product.description}</p>}

      <VariantPicker
        variants={product.variants}
        selectedVariantId={selectedVariantId}
        onSelect={setPickedVariantId}
      />

      <ActionBar label={buttonLabel} onClick={handleAddToCart} disabled={outOfStock} />
    </div>
  )
}
