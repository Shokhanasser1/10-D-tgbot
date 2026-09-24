import { type ComponentProps, lazy, Suspense } from 'react'

import { Skeleton } from '../ui/Skeleton'

const TrackingMap = lazy(() =>
  import('./TrackingMap').then((module) => ({ default: module.TrackingMap })),
)

export function LazyTrackingMap(props: ComponentProps<typeof TrackingMap>) {
  return (
    <Suspense fallback={<Skeleton height={240} radius="18px" />}>
      <TrackingMap {...props} />
    </Suspense>
  )
}
