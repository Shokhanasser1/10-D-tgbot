import { createBrowserRouter } from 'react-router-dom'

import { AppShell } from './AppShell'

function Placeholder({ label }: { label: string }) {
  return <div style={{ padding: '24px 0' }}>{label}</div>
}

export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppShell />,
    children: [
      { index: true, element: <Placeholder label="Catalog" /> },
      { path: 'products/:productId', element: <Placeholder label="Product" /> },
      { path: 'cart', element: <Placeholder label="Cart" /> },
      { path: 'checkout', element: <Placeholder label="Checkout" /> },
      { path: 'orders', element: <Placeholder label="Orders" /> },
      { path: 'orders/:orderId', element: <Placeholder label="Order detail" /> },
    ],
  },
])
