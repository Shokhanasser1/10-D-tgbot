export interface Category {
  id: number
  slug: string
  parent_id: number | null
  sort_order: number
  name: string
}

/** Whose product it is (Spec 9). */
export interface SellerBrief {
  id: number
  name: string
}

export interface ProductListItem {
  id: number
  category_id: number
  seller: SellerBrief
  base_sku: string
  base_price: string
  name: string
  thumbnail_url: string | null
}

export interface Variant {
  id: number
  sku: string
  price: string
  stock_qty: number
  attribute_values: Record<string, string>
  image_urls: string[]
}

export interface ProductDetail {
  id: number
  category_id: number
  seller: SellerBrief
  base_sku: string
  base_price: string
  name: string
  description: string | null
  image_urls: string[]
  variants: Variant[]
}
