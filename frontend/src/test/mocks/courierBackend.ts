import { http, HttpResponse } from 'msw'

import type { CourierDelivery, PoolItem } from '../../features/courier/types'
import { courierProfile, poolItems } from '../fixtures'
import { API } from './handlers'
import { server } from './server'

interface CourierBackendOptions {
  pool?: PoolItem[]
  deliveries?: CourierDelivery[]
  locationUpdatedAt?: string | null
  botUsername?: string | null
}

export interface Action {
  step: string
  shipmentId: number
}

/**
 * A small in-memory courier API for tests: claiming moves an order from the pool into the
 * courier's deliveries, and so on, so a screen can be driven through a whole flow. Individual
 * tests override single endpoints with `server.use` to simulate failures.
 */
export function stubCourierBackend(options: CourierBackendOptions = {}) {
  const state = {
    pool: [...(options.pool ?? poolItems)],
    deliveries: [...(options.deliveries ?? [])],
    locationUpdatedAt: options.locationUpdatedAt ?? null,
    actions: [] as Action[],
  }

  server.use(
    http.get(`${API}/courier/me`, () =>
      HttpResponse.json({
        ...courierProfile,
        bot_username: options.botUsername === undefined ? 'shop_courier_bot' : options.botUsername,
      }),
    ),
    http.get(`${API}/courier/pool`, () => HttpResponse.json(state.pool)),
    http.get(`${API}/courier/deliveries`, () =>
      HttpResponse.json({
        location_updated_at: state.locationUpdatedAt,
        deliveries: state.deliveries,
      }),
    ),
    http.post(`${API}/courier/deliveries/:id/:step`, ({ params }) => {
      const shipmentId = Number(params.id)
      const step = String(params.step)
      state.actions.push({ step, shipmentId })

      const poolItem = state.pool.find((item) => item.shipment_id === shipmentId)
      const delivery = state.deliveries.find((item) => item.shipment_id === shipmentId)

      if (step === 'claim' && poolItem) {
        state.pool = state.pool.filter((item) => item !== poolItem)
        state.deliveries = [...state.deliveries, deliveryFor(poolItem)]
      } else if (step === 'pickup' && delivery) {
        state.deliveries = state.deliveries.map((item) =>
          item === delivery ? { ...item, status: 'shipped' } : item,
        )
      } else if (step === 'deliver' && delivery) {
        state.deliveries = state.deliveries.filter((item) => item !== delivery)
      } else if (step === 'release' && delivery) {
        state.deliveries = state.deliveries.filter((item) => item !== delivery)
        state.pool = [...state.pool, poolItemFor(delivery)]
      }

      return HttpResponse.json({ shipment_id: shipmentId, order_id: 0, status: step })
    }),
  )

  return state
}

function deliveryFor(item: PoolItem): CourierDelivery {
  return {
    shipment_id: item.shipment_id,
    order_id: item.order_id,
    status: 'assigned',
    address: {
      street: item.street,
      city: item.city,
      postal_code: '10178',
      country: 'DE',
      phone: '+49 123 4567',
      notes: null,
    },
    destination: null,
    items: [{ name: 'Velvet Matte Lipstick', qty: item.item_count }],
    assigned_at: '2026-09-24T10:10:00Z',
    picked_up_at: null,
    pickup: item.pickup,
  }
}

function poolItemFor(delivery: CourierDelivery): PoolItem {
  return {
    shipment_id: delivery.shipment_id,
    order_id: delivery.order_id,
    city: delivery.address.city,
    street: delivery.address.street,
    item_count: delivery.items.length,
    placed_at: '2026-09-24T10:00:00Z',
    pickup: delivery.pickup,
  }
}
