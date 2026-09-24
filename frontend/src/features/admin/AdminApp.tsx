import { useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'
import { Navigate, Route, Routes, useParams } from 'react-router-dom'

import { QueryError } from '../../shared/ui/QueryError'
import { Skeleton } from '../../shared/ui/Skeleton'
import { AdminLayout } from './components/AdminLayout'
import { isStatus } from './errors'
import { adminKeys, useAdminMe } from './hooks'
import { canOpen, homeFor } from './permissions'
import { AdminsScreen } from './screens/AdminsScreen'
import { LoginScreen, NoAccessScreen } from './screens/AuthScreens'
import { CategoriesScreen } from './screens/CategoriesScreen'
import { CouriersScreen } from './screens/CouriersScreen'
import { OrderDetailScreen } from './screens/OrderDetailScreen'
import { OrdersScreen } from './screens/OrdersScreen'
import { ProductEditorScreen } from './screens/ProductEditorScreen'
import { ProductsScreen } from './screens/ProductsScreen'
import { SummaryScreen } from './screens/SummaryScreen'

/**
 * A session can end while the panel is open (it expired, or an owner removed this admin).
 * Any admin request answering 401 or 403 then re-asks who is signed in, which routes to the
 * sign-in or no-access screen instead of leaving broken screens behind.
 */
function useSessionWatch() {
  const queryClient = useQueryClient()

  useEffect(() => {
    const cache = queryClient.getQueryCache()
    return cache.subscribe((event) => {
      if (event.type !== 'updated' || event.action.type !== 'error') return
      const [scope, what] = event.query.queryKey as unknown[]
      if (scope !== 'admin' || what === 'me') return
      const error = event.action.error
      if (isStatus(error, 401) || isStatus(error, 403)) {
        void queryClient.invalidateQueries({ queryKey: adminKeys.me })
      }
    })
  }, [queryClient])
}

function ProductEditorRoute() {
  // Remount per product so the form never carries one product's edits into another.
  const { productId } = useParams<{ productId: string }>()
  return <ProductEditorScreen key={productId} productId={Number(productId)} />
}

export function AdminApp() {
  const meQuery = useAdminMe()
  useSessionWatch()

  if (meQuery.isLoading) {
    return (
      <div style={{ padding: 16 }}>
        <Skeleton height={48} />
      </div>
    )
  }
  if (isStatus(meQuery.error, 401)) return <LoginScreen />
  if (isStatus(meQuery.error, 403)) return <NoAccessScreen />
  if (meQuery.isError || !meQuery.data) return <QueryError onRetry={() => meQuery.refetch()} />

  const me = meQuery.data
  const { role } = me
  const home = <Navigate to={`/admin/${homeFor(role)}`} replace />

  return (
    <AdminLayout me={me}>
      <Routes>
        <Route index element={home} />
        {canOpen(role, 'summary') && <Route path="summary" element={<SummaryScreen />} />}
        {canOpen(role, 'catalog') && (
          <>
            <Route path="catalog" element={<ProductsScreen />} />
            <Route path="catalog/new" element={<ProductEditorScreen productId={null} />} />
            <Route path="catalog/products/:productId" element={<ProductEditorRoute />} />
            <Route path="catalog/categories" element={<CategoriesScreen />} />
          </>
        )}
        {canOpen(role, 'orders') && (
          <>
            <Route path="orders" element={<OrdersScreen />} />
            <Route path="orders/:orderId" element={<OrderDetailScreen />} />
          </>
        )}
        {canOpen(role, 'couriers') && <Route path="couriers" element={<CouriersScreen />} />}
        {canOpen(role, 'admins') && (
          <Route path="admins" element={<AdminsScreen currentTelegramId={me.telegram_id} />} />
        )}
        <Route path="*" element={home} />
      </Routes>
    </AdminLayout>
  )
}
