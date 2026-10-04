import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import * as api from './api'
import type { OrderFilters, StatsPeriod } from './types'

export const adminKeys = {
  me: ['admin', 'me'] as const,
  admins: ['admin', 'admins'] as const,
  categories: ['admin', 'categories'] as const,
  attributes: ['admin', 'attributes'] as const,
  products: ['admin', 'products'] as const,
  product: (id: number) => ['admin', 'product', id] as const,
  orders: ['admin', 'orders'] as const,
  order: (id: number) => ['admin', 'order', id] as const,
  couriers: ['admin', 'couriers'] as const,
  sellers: ['admin', 'sellers'] as const,
  shipments: ['admin', 'shipments'] as const,
  locations: ['admin', 'locations'] as const,
  summary: ['admin', 'summary'] as const,
}

const LIST_POLL_MS = 10_000

function useLocale(): string {
  return useTranslation().i18n.language
}

export function useAdminMe() {
  return useQuery({ queryKey: adminKeys.me, queryFn: api.fetchMe, retry: false, staleTime: 60_000 })
}

export function useLogin() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: api.loginWithTelegram,
    onSuccess: (me) => queryClient.setQueryData(adminKeys.me, me),
  })
}

export function usePasswordLogin() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: api.loginWithPassword,
    onSuccess: (me) => queryClient.setQueryData(adminKeys.me, me),
  })
}

export function useChangePassword() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: api.changeMyPassword,
    onSuccess: (me) => queryClient.setQueryData(adminKeys.me, me),
  })
}

export function useLogout() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: api.logout,
    // Drop everything cached for the previous admin, then ask again who is here.
    onSettled: async () => {
      queryClient.removeQueries({ queryKey: ['admin'] })
      await queryClient.invalidateQueries({ queryKey: adminKeys.me })
    },
  })
}

// --- catalog ---------------------------------------------------------------------------------

export function useAdminCategories() {
  const locale = useLocale()
  return useQuery({
    queryKey: [...adminKeys.categories, locale],
    queryFn: () => api.fetchCategories(locale),
  })
}

export function useAdminAttributes() {
  return useQuery({ queryKey: adminKeys.attributes, queryFn: api.fetchAttributes })
}

export function useAdminProducts(filters: api.ProductFilters) {
  const locale = useLocale()
  return useQuery({
    queryKey: [...adminKeys.products, filters, locale],
    queryFn: () => api.fetchProducts(filters, locale),
    placeholderData: keepPreviousData,
  })
}

export function useAdminProduct(id: number | null) {
  const locale = useLocale()
  return useQuery({
    queryKey: [...adminKeys.product(id ?? 0), locale],
    queryFn: () => api.fetchProduct(id as number, locale),
    enabled: id !== null,
  })
}

/** Runs a catalog write and refreshes every catalog view it may have changed. */
export function useCatalogMutation<TArgs, TResult>(fn: (args: TArgs) => Promise<TResult>) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: () =>
      Promise.all(
        [adminKeys.products, ['admin', 'product'], adminKeys.categories, adminKeys.attributes].map(
          (queryKey) => queryClient.invalidateQueries({ queryKey }),
        ),
      ),
  })
}

// --- sellers ---------------------------------------------------------------------------------

export function useAdminSellers(enabled = true) {
  return useQuery({ queryKey: adminKeys.sellers, queryFn: api.fetchSellers, enabled })
}

/** A seller write also changes what the catalog shows (names, hidden products). */
export function useSellerMutation<TArgs, TResult>(fn: (args: TArgs) => Promise<TResult>) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: () =>
      Promise.all(
        [adminKeys.sellers, adminKeys.products, adminKeys.admins].map((queryKey) =>
          queryClient.invalidateQueries({ queryKey }),
        ),
      ),
  })
}

// --- orders ----------------------------------------------------------------------------------

export function useAdminOrders(filters: OrderFilters) {
  return useQuery({
    queryKey: [...adminKeys.orders, filters],
    queryFn: () => api.fetchOrders(filters),
    placeholderData: keepPreviousData,
    refetchInterval: LIST_POLL_MS,
    staleTime: 0,
  })
}

export function useAdminOrder(id: number) {
  return useQuery({
    queryKey: adminKeys.order(id),
    queryFn: () => api.fetchOrder(id),
    enabled: Number.isFinite(id),
    refetchInterval: LIST_POLL_MS,
    staleTime: 0,
  })
}

export function useOrderAction<TArgs>(fn: (args: TArgs) => ReturnType<typeof api.fetchOrder>) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: (order) => queryClient.setQueryData(adminKeys.order(order.id), order),
    onSettled: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: adminKeys.orders }),
        queryClient.invalidateQueries({ queryKey: adminKeys.summary }),
        queryClient.invalidateQueries({ queryKey: adminKeys.shipments }),
      ]),
  })
}

// --- couriers --------------------------------------------------------------------------------

export function useAdminCouriers() {
  return useQuery({
    queryKey: adminKeys.couriers,
    queryFn: api.fetchCouriers,
    refetchInterval: LIST_POLL_MS,
    staleTime: 0,
  })
}

export function useAdminShipments() {
  return useQuery({
    queryKey: adminKeys.shipments,
    queryFn: api.fetchShipments,
    refetchInterval: LIST_POLL_MS,
    staleTime: 0,
  })
}

export function useCourierLocations() {
  return useQuery({
    queryKey: adminKeys.locations,
    queryFn: api.fetchCourierLocations,
    refetchInterval: LIST_POLL_MS,
    staleTime: 0,
  })
}

export function useDispatchMutation<TArgs, TResult>(fn: (args: TArgs) => Promise<TResult>) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: fn,
    // Also on failure: a 409 means someone else changed the delivery meanwhile.
    onSettled: () =>
      Promise.all(
        [adminKeys.couriers, adminKeys.shipments, adminKeys.locations, adminKeys.orders].map(
          (queryKey) => queryClient.invalidateQueries({ queryKey }),
        ),
      ),
  })
}

// --- summary and admins ----------------------------------------------------------------------

export function useSummary(period: StatsPeriod) {
  return useQuery({
    queryKey: [...adminKeys.summary, period],
    queryFn: () => api.fetchSummary(period),
    refetchInterval: 60_000,
  })
}

export function useAdmins() {
  return useQuery({ queryKey: adminKeys.admins, queryFn: api.fetchAdmins })
}

export function useAdminsMutation<TArgs, TResult>(fn: (args: TArgs) => Promise<TResult>) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSettled: () => queryClient.invalidateQueries({ queryKey: adminKeys.admins }),
  })
}
