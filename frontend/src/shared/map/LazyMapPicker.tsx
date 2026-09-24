import { type ComponentProps, lazy, Suspense } from 'react'

import { Skeleton } from '../ui/Skeleton'

// Leaflet and its stylesheet are only fetched when a map is actually about to be shown.
const MapPicker = lazy(() =>
  import('./MapPicker').then((module) => ({ default: module.MapPicker })),
)

export function LazyMapPicker(props: ComponentProps<typeof MapPicker>) {
  return (
    <Suspense fallback={<Skeleton height={240} radius="18px" />}>
      <MapPicker {...props} />
    </Suspense>
  )
}
