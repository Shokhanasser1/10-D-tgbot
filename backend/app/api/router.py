from fastapi import APIRouter

api_router = APIRouter()

# Feature routers are mounted here as they're implemented:
# from app.api.routes import catalog, cart, checkout, orders, webhooks, internal_products
# api_router.include_router(catalog.router)
