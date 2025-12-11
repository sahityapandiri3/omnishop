"""
Admin migration endpoints for one-time database updates.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/migrations", tags=["admin"])


@router.post("/migrate-bedside-tables")
async def migrate_bedside_tables(db: AsyncSession = Depends(get_db)):
    """
    One-time migration to categorize bedside table products into Bedside Tables category.
    """
    try:
        # Check current state
        result = await db.execute(text("""
            SELECT p.category_id, c.name as category_name, COUNT(*) as product_count
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE LOWER(p.name) LIKE '%bedside%' OR LOWER(p.name) LIKE '%nightstand%' OR LOWER(p.name) LIKE '%night stand%'
            GROUP BY p.category_id, c.name
            ORDER BY product_count DESC;
        """))
        before_state = [{"category_id": row[0], "category_name": row[1], "count": row[2]} for row in result]

        # Find Bedside Tables category
        result = await db.execute(text("SELECT id, name FROM categories WHERE slug = 'bedside-tables';"))
        bedside_category = result.fetchone()

        if not bedside_category:
            raise HTTPException(status_code=404, detail="Bedside Tables category not found")

        bedside_category_id = bedside_category[0]

        # Update products
        result = await db.execute(text(f"""
            UPDATE products
            SET category_id = {bedside_category_id}
            WHERE LOWER(name) LIKE '%bedside%' OR LOWER(name) LIKE '%nightstand%' OR LOWER(name) LIKE '%night stand%';
        """))
        await db.commit()
        updated_count = result.rowcount

        # Check final state
        result = await db.execute(text("""
            SELECT p.category_id, c.name as category_name, COUNT(*) as product_count
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE LOWER(p.name) LIKE '%bedside%' OR LOWER(p.name) LIKE '%nightstand%' OR LOWER(p.name) LIKE '%night stand%'
            GROUP BY p.category_id, c.name
            ORDER BY product_count DESC;
        """))
        after_state = [{"category_id": row[0], "category_name": row[1], "count": row[2]} for row in result]

        return {
            "success": True,
            "message": f"Migrated {updated_count} products to Bedside Tables category (id={bedside_category_id})",
            "before": before_state,
            "after": after_state
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Migration error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Migration failed: {str(e)}")
