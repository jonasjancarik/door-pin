from fastapi import APIRouter
import logging  # Import logging

router = APIRouter()
logger = logging.getLogger("api.health")  # Get a logger specific to this module


@router.get("/health", tags=["health"])
async def health_check():
    """
    Health check endpoint.
    """
    logger.info("Health check endpoint was called.")
    return {"status": "ok"}
