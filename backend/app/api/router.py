from fastapi import APIRouter

from app.api.routes import (
    cart,
    catalog,
    checkout,
    courier,
    internal_admins,
    internal_auth,
    internal_couriers,
    internal_orders,
    internal_products,
    internal_sellers,
    internal_stats,
    orders,
    webhooks,
)

api_router = APIRouter()
api_router.include_router(catalog.router)
api_router.include_router(cart.router)
api_router.include_router(checkout.router)
api_router.include_router(orders.router)
api_router.include_router(courier.router)
api_router.include_router(webhooks.router)
api_router.include_router(internal_auth.router)
api_router.include_router(internal_admins.router)
api_router.include_router(internal_products.router)
api_router.include_router(internal_sellers.router)
api_router.include_router(internal_couriers.router)
api_router.include_router(internal_orders.router)
api_router.include_router(internal_stats.router)
