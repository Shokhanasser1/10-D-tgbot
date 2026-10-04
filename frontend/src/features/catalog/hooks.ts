import { useQuery } from '@tanstack/react-query'

import { fetchCategories, fetchProduct, fetchProducts } from './api'

export function useCategories() {
  return useQuery({ queryKey: ['categories'], queryFn: fetchCategories })
}

export function useProducts(categoryId?: number, sellerId?: number) {
  return useQuery({
    queryKey: ['products', categoryId, sellerId],
    queryFn: () => fetchProducts(categoryId, sellerId),
  })
}

export function useProduct(productId: number) {
  return useQuery({
    queryKey: ['product', productId],
    queryFn: () => fetchProduct(productId),
    enabled: Number.isFinite(productId),
  })
}
