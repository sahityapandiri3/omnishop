"""
Stores API routes for store/source management
"""
import logging
from typing import List

from core.database import get_db
from database.models import Product
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/stores", tags=["stores"])


class StoresResponse(BaseModel):
    """Response model for stores list"""

    stores: List[str]


@router.get("", response_model=StoresResponse)
async def get_available_stores(db: AsyncSession = Depends(get_db)):
    """
    Get list of unique stores that have available products
    Returns stores sorted alphabetically
    """
    try:
        logger.info("Fetching available stores with products")

        # Query for distinct source_website where products are available
        query = select(Product.source_website).where(Product.is_available == True).distinct()  # noqa: E712

        result = await db.execute(query)
        stores = [row[0] for row in result.fetchall() if row[0]]  # Filter out None values

        # Sort alphabetically for consistent ordering
        stores_sorted = sorted(stores)

        logger.info(f"Found {len(stores_sorted)} available stores: {stores_sorted}")

        return StoresResponse(stores=stores_sorted)

    except Exception as e:
        logger.error(f"Error fetching available stores: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch stores: {str(e)}")
