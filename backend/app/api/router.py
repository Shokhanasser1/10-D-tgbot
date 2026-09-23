from fastapi import APIRouter

from app.api.routes import cart, catalog, checkout, internal_products, webhooks

api_router = APIRouter()
api_router.include_router(catalog.router)
api_router.include_router(cart.router)
api_router.include_router(checkout.router)
api_router.include_router(webhooks.router)
api_router.include_router(internal_products.router)

# Mounted here as it's implemented:
# from app.api.routes import orders
