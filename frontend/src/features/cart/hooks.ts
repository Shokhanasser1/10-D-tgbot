import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { addCartItem, fetchCart, removeCartItem, updateCartItem } from './api'
import type { Cart } from './types'

const CART_KEY = ['cart']

export function useCart() {
  return useQuery({ queryKey: CART_KEY, queryFn: fetchCart })
}

export function useAddCartItem() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      variantId,
      qty,
      replaceCart = false,
    }: {
      variantId: number
      qty: number
      replaceCart?: boolean
    }) => addCartItem(variantId, qty, replaceCart),
    onSuccess: (cart: Cart) => queryClient.setQueryData(CART_KEY, cart),
  })
}

export function useUpdateCartItem() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ itemId, qty }: { itemId: number; qty: number }) => updateCartItem(itemId, qty),
    onSuccess: (cart: Cart) => queryClient.setQueryData(CART_KEY, cart),
  })
}

export function useRemoveCartItem() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (itemId: number) => removeCartItem(itemId),
    onSuccess: (cart: Cart) => queryClient.setQueryData(CART_KEY, cart),
  })
}
