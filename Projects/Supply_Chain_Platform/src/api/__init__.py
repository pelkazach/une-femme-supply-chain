"""FastAPI routes for the supply chain platform."""

from src.api.inventory import router as inventory_router

__all__ = ["inventory_router"]
