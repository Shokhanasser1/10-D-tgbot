from fastapi import APIRouter

from app.api.routes import catalog, internal_products

api_router = APIRouter()
api_router.include_router(catalog.router)
api_router.include_router(internal_products.router)

# Mounted here as they're implemented:
# from app.api.routes import cart, checkout, orders, webhooks
