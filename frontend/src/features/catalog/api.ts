import { apiFetch } from '../../shared/api/client'
import type { Category, ProductDetail, ProductListItem } from './types'

export function fetchCategories(): Promise<Category[]> {
  return apiFetch<Category[]>('/catalog/categories')
}

export function fetchProducts(categoryId?: number): Promise<ProductListItem[]> {
  return apiFetch<ProductListItem[]>('/catalog/products', { params: { category: categoryId } })
}

export function fetchProduct(productId: number): Promise<ProductDetail> {
  return apiFetch<ProductDetail>(`/catalog/products/${productId}`)
}
