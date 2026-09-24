import { useQuery } from '@tanstack/react-query'

import { fetchCategories, fetchProduct, fetchProducts } from './api'

export function useCategories() {
  return useQuery({ queryKey: ['categories'], queryFn: fetchCategories })
}

export function useProducts(categoryId?: number) {
  return useQuery({
    queryKey: ['products', categoryId],
    queryFn: () => fetchProducts(categoryId),
  })
}

export function useProduct(productId: number) {
  return useQuery({
    queryKey: ['product', productId],
    queryFn: () => fetchProduct(productId),
    enabled: Number.isFinite(productId),
  })
}
