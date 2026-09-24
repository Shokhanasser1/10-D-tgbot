import { createBrowserRouter, useParams } from 'react-router-dom'

import { CartScreen } from '../features/cart/screens/CartScreen'
import { CatalogHomeScreen } from '../features/catalog/screens/CatalogHomeScreen'
import { ProductDetailScreen } from '../features/catalog/screens/ProductDetailScreen'
import { CheckoutScreen } from '../features/checkout/screens/CheckoutScreen'
import { OrderDetailScreen } from '../features/orders/screens/OrderDetailScreen'
import { OrdersListScreen } from '../features/orders/screens/OrdersListScreen'
import { AppShell } from './AppShell'

function ProductDetailRoute() {
  // Remounts on navigation between products (same route element otherwise reuses local state).
  const { productId } = useParams<{ productId: string }>()
  return <ProductDetailScreen key={productId} />
}

export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppShell />,
    children: [
      { index: true, element: <CatalogHomeScreen /> },
      { path: 'products/:productId', element: <ProductDetailRoute /> },
      { path: 'cart', element: <CartScreen /> },
      { path: 'checkout', element: <CheckoutScreen /> },
      { path: 'orders', element: <OrdersListScreen /> },
      { path: 'orders/:orderId', element: <OrderDetailScreen /> },
    ],
  },
])
