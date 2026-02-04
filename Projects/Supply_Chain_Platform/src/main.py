"""FastAPI application entry point."""

from fastapi import FastAPI

from src.api.inventory import router as inventory_router
from src.api.metrics import router as metrics_router
from src.api.review import router as review_router
from src.api.upload import router as upload_router
from src.config import settings

app = FastAPI(
    title="Une Femme Supply Chain Platform",
    description="Supply chain intelligence platform for inventory tracking and forecasting",
    version="0.1.0",
    debug=settings.debug,
)

# Include API routers
app.include_router(inventory_router)
app.include_router(metrics_router)
app.include_router(review_router)
app.include_router(upload_router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}
