"""
Admin migration endpoints for one-time database updates.
Includes backfill operations for embeddings and style classification.
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from core.database import get_db
from database.models import Product

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/migrations", tags=["admin"])


# =====================================================================
# BACKFILL STATE TRACKING
# =====================================================================

class BackfillState:
    """Track state of background backfill operations."""

    def __init__(self):
        self.embeddings: Dict = {"status": "idle", "progress": {}}
        self.styles: Dict = {"status": "idle", "progress": {}}

    def update_embeddings(self, status: str, **kwargs):
        self.embeddings["status"] = status
        self.embeddings["progress"].update(kwargs)
        self.embeddings["updated_at"] = datetime.utcnow().isoformat()

    def update_styles(self, status: str, **kwargs):
        self.styles["status"] = status
        self.styles["progress"].update(kwargs)
        self.styles["updated_at"] = datetime.utcnow().isoformat()


# Global state tracker
backfill_state = BackfillState()


class BackfillRequest(BaseModel):
    """Request model for backfill operations."""
    batch_size: int = 100
    limit: Optional[int] = None
    regenerate: bool = False


# =====================================================================
# EMBEDDING BACKFILL ENDPOINTS
# =====================================================================

async def _run_embedding_backfill(
    batch_size: int,
    limit: Optional[int],
    regenerate: bool
):
    """Background task to run embedding backfill."""
    from services.embedding_service import get_embedding_service
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from core.config import settings

    embedding_service = get_embedding_service()
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    Session = sessionmaker(bind=engine)

    try:
        backfill_state.update_embeddings("running", started_at=datetime.utcnow().isoformat())

        session = Session()
        try:
            # Get products needing embeddings
            query = session.query(Product.id).filter(Product.is_available.is_(True))
            if not regenerate:
                query = query.filter(Product.embedding.is_(None))
            query = query.order_by(Product.id)
            if limit:
                query = query.limit(limit)

            product_ids = [row[0] for row in query.all()]
            total = len(product_ids)

            backfill_state.update_embeddings(
                "running",
                total=total,
                processed=0,
                success=0,
                failed=0
            )

            logger.info(f"[EMBEDDING BACKFILL] Starting backfill for {total} products")

            processed = 0
            success = 0
            failed = 0

            for i in range(0, total, batch_size):
                batch_ids = product_ids[i:i + batch_size]

                for product_id in batch_ids:
                    try:
                        product = session.query(Product).filter(Product.id == product_id).first()
                        if not product:
                            continue

                        # Build embedding text
                        embedding_text = embedding_service.build_product_embedding_text(product)

                        # Generate embedding
                        embedding = await embedding_service.generate_embedding(
                            embedding_text,
                            task_type="RETRIEVAL_DOCUMENT"
                        )

                        if embedding:
                            product.embedding = json.dumps(embedding)
                            product.embedding_text = embedding_text
                            product.embedding_updated_at = datetime.utcnow()
                            success += 1
                        else:
                            failed += 1

                    except Exception as e:
                        logger.error(f"Error processing product {product_id}: {e}")
                        failed += 1

                    processed += 1
                    await asyncio.sleep(0.5)  # Rate limiting

                session.commit()

                backfill_state.update_embeddings(
                    "running",
                    processed=processed,
                    success=success,
                    failed=failed,
                    percent_complete=round(processed / total * 100, 1) if total > 0 else 0
                )

            session.commit()

        finally:
            session.close()

        backfill_state.update_embeddings(
            "completed",
            processed=processed,
            success=success,
            failed=failed,
            completed_at=datetime.utcnow().isoformat()
        )
        logger.info(f"[EMBEDDING BACKFILL] Completed: {success}/{total} successful")

    except Exception as e:
        logger.error(f"[EMBEDDING BACKFILL] Failed: {e}", exc_info=True)
        backfill_state.update_embeddings("failed", error=str(e))


@router.post("/backfill/embeddings")
async def start_embedding_backfill(
    request: BackfillRequest,
    background_tasks: BackgroundTasks
):
    """
    Start background embedding generation for products.

    This processes products in batches, generating vector embeddings
    using Google text-embedding-004 for semantic search.
    """
    if backfill_state.embeddings["status"] == "running":
        raise HTTPException(
            status_code=409,
            detail="Embedding backfill is already running"
        )

    background_tasks.add_task(
        _run_embedding_backfill,
        request.batch_size,
        request.limit,
        request.regenerate
    )

    backfill_state.update_embeddings("starting")

    return {
        "message": "Embedding backfill started",
        "batch_size": request.batch_size,
        "limit": request.limit,
        "regenerate": request.regenerate
    }


# =====================================================================
# STYLE CLASSIFICATION BACKFILL ENDPOINTS
# =====================================================================

async def _run_style_backfill(
    batch_size: int,
    limit: Optional[int]
):
    """Background task to run style classification backfill."""
    from services.google_ai_service import google_ai_service
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from core.config import settings
    from database.models import ProductImage

    engine = create_engine(settings.database_url, pool_pre_ping=True)
    Session = sessionmaker(bind=engine)

    try:
        backfill_state.update_styles("running", started_at=datetime.utcnow().isoformat())

        session = Session()
        try:
            # Get products needing style classification
            query = (
                session.query(Product.id)
                .filter(Product.is_available.is_(True))
                .filter(Product.primary_style.is_(None))
                .order_by(Product.id)
            )
            if limit:
                query = query.limit(limit)

            product_ids = [row[0] for row in query.all()]
            total = len(product_ids)

            backfill_state.update_styles(
                "running",
                total=total,
                processed=0,
                success_vision=0,
                success_text=0,
                failed=0
            )

            logger.info(f"[STYLE BACKFILL] Starting backfill for {total} products")

            processed = 0
            success_vision = 0
            success_text = 0
            failed = 0

            for i in range(0, total, batch_size):
                batch_ids = product_ids[i:i + batch_size]

                for product_id in batch_ids:
                    try:
                        product = session.query(Product).filter(Product.id == product_id).first()
                        if not product:
                            continue

                        # Get primary image URL
                        image = (
                            session.query(ProductImage)
                            .filter(ProductImage.product_id == product_id)
                            .filter(ProductImage.is_primary == True)
                            .first()
                        )
                        image_url = ""
                        if image:
                            image_url = image.large_url or image.medium_url or image.original_url or ""

                        # Classify style
                        result = await google_ai_service.classify_product_style(
                            image_url=image_url,
                            product_name=product.name or "",
                            product_description=product.description or ""
                        )

                        # Update product
                        product.primary_style = result.get("primary_style")
                        product.secondary_style = result.get("secondary_style")
                        product.style_confidence = result.get("confidence", 0.0)

                        if image_url and result.get("confidence", 0) > 0.4:
                            product.style_extraction_method = "gemini_vision"
                            success_vision += 1
                        else:
                            product.style_extraction_method = "text_nlp"
                            success_text += 1

                    except Exception as e:
                        logger.error(f"Error processing product {product_id}: {e}")
                        failed += 1

                    processed += 1
                    await asyncio.sleep(1.0)  # Rate limiting for vision API

                session.commit()

                backfill_state.update_styles(
                    "running",
                    processed=processed,
                    success_vision=success_vision,
                    success_text=success_text,
                    failed=failed,
                    percent_complete=round(processed / total * 100, 1) if total > 0 else 0
                )

            session.commit()

        finally:
            session.close()

        backfill_state.update_styles(
            "completed",
            processed=processed,
            success_vision=success_vision,
            success_text=success_text,
            failed=failed,
            completed_at=datetime.utcnow().isoformat()
        )
        logger.info(f"[STYLE BACKFILL] Completed: vision={success_vision}, text={success_text}, failed={failed}")

    except Exception as e:
        logger.error(f"[STYLE BACKFILL] Failed: {e}", exc_info=True)
        backfill_state.update_styles("failed", error=str(e))


@router.post("/backfill/styles")
async def start_style_backfill(
    request: BackfillRequest,
    background_tasks: BackgroundTasks
):
    """
    Start background style classification for products.

    This processes products in batches, classifying their design style
    using Gemini Vision API with text-based fallback.
    """
    if backfill_state.styles["status"] == "running":
        raise HTTPException(
            status_code=409,
            detail="Style backfill is already running"
        )

    background_tasks.add_task(
        _run_style_backfill,
        request.batch_size,
        request.limit
    )

    backfill_state.update_styles("starting")

    return {
        "message": "Style backfill started",
        "batch_size": request.batch_size,
        "limit": request.limit
    }


@router.get("/backfill/status")
async def get_backfill_status():
    """Get status of all backfill operations."""
    return {
        "embeddings": backfill_state.embeddings,
        "styles": backfill_state.styles
    }


@router.get("/backfill/stats")
async def get_backfill_stats(db: AsyncSession = Depends(get_db)):
    """Get statistics about embeddings and styles in the database."""
    # Count products with/without embeddings
    embedding_stats = await db.execute(
        text("""
            SELECT
                COUNT(*) as total,
                COUNT(embedding) as with_embedding,
                COUNT(*) - COUNT(embedding) as without_embedding
            FROM products
            WHERE is_available = true
        """)
    )
    emb_row = embedding_stats.fetchone()

    # Count products with/without styles
    style_stats = await db.execute(
        text("""
            SELECT
                COUNT(*) as total,
                COUNT(primary_style) as with_style,
                COUNT(*) - COUNT(primary_style) as without_style
            FROM products
            WHERE is_available = true
        """)
    )
    style_row = style_stats.fetchone()

    # Style distribution
    style_distribution = await db.execute(
        text("""
            SELECT primary_style, COUNT(*) as count
            FROM products
            WHERE is_available = true AND primary_style IS NOT NULL
            GROUP BY primary_style
            ORDER BY count DESC
        """)
    )
    style_dist = [{"style": row[0], "count": row[1]} for row in style_distribution.fetchall()]

    return {
        "embeddings": {
            "total_products": emb_row[0],
            "with_embedding": emb_row[1],
            "without_embedding": emb_row[2],
            "percent_complete": round(emb_row[1] / emb_row[0] * 100, 1) if emb_row[0] > 0 else 0
        },
        "styles": {
            "total_products": style_row[0],
            "with_style": style_row[1],
            "without_style": style_row[2],
            "percent_complete": round(style_row[1] / style_row[0] * 100, 1) if style_row[0] > 0 else 0,
            "distribution": style_dist
        }
    }


@router.post("/migrate-bedside-tables")
async def migrate_bedside_tables(db: AsyncSession = Depends(get_db)):
    """
    One-time migration to categorize bedside table products into Bedside Tables category.
    """
    try:
        # Check current state
        result = await db.execute(
            text(
                """
            SELECT p.category_id, c.name as category_name, COUNT(*) as product_count
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE LOWER(p.name) LIKE '%bedside%' OR LOWER(p.name) LIKE '%nightstand%' OR LOWER(p.name) LIKE '%night stand%'
            GROUP BY p.category_id, c.name
            ORDER BY product_count DESC;
        """
            )
        )
        before_state = [{"category_id": row[0], "category_name": row[1], "count": row[2]} for row in result]

        # Find Bedside Tables category
        result = await db.execute(text("SELECT id, name FROM categories WHERE slug = 'bedside-tables';"))
        bedside_category = result.fetchone()

        if not bedside_category:
            raise HTTPException(status_code=404, detail="Bedside Tables category not found")

        bedside_category_id = bedside_category[0]

        # Update products
        result = await db.execute(
            text(
                f"""
            UPDATE products
            SET category_id = {bedside_category_id}
            WHERE LOWER(name) LIKE '%bedside%' OR LOWER(name) LIKE '%nightstand%' OR LOWER(name) LIKE '%night stand%';
        """
            )
        )
        await db.commit()
        updated_count = result.rowcount

        # Check final state
        result = await db.execute(
            text(
                """
            SELECT p.category_id, c.name as category_name, COUNT(*) as product_count
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE LOWER(p.name) LIKE '%bedside%' OR LOWER(p.name) LIKE '%nightstand%' OR LOWER(p.name) LIKE '%night stand%'
            GROUP BY p.category_id, c.name
            ORDER BY product_count DESC;
        """
            )
        )
        after_state = [{"category_id": row[0], "category_name": row[1], "count": row[2]} for row in result]

        return {
            "success": True,
            "message": f"Migrated {updated_count} products to Bedside Tables category (id={bedside_category_id})",
            "before": before_state,
            "after": after_state,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Migration error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Migration failed: {str(e)}")


@router.post("/migrate-table-mats")
async def migrate_table_mats(db: AsyncSession = Depends(get_db)):
    """
    One-time migration to:
    1. Create Table Mats category if it doesn't exist
    2. Migrate placemat and table runner products into Table Mats category
    """
    try:
        # Check current state of placemat/runner products
        result = await db.execute(
            text(
                """
            SELECT p.category_id, c.name as category_name, COUNT(*) as product_count
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE LOWER(p.name) LIKE '%placemat%'
               OR LOWER(p.name) LIKE '%table mat%'
               OR (LOWER(p.name) LIKE '%runner%' AND LOWER(p.name) NOT LIKE '%floor runner%')
            GROUP BY p.category_id, c.name
            ORDER BY product_count DESC;
        """
            )
        )
        before_state = [{"category_id": row[0], "category_name": row[1], "count": row[2]} for row in result]

        # Check if Table Mats category exists
        result = await db.execute(text("SELECT id, name FROM categories WHERE slug = 'table-mats';"))
        table_mats_category = result.fetchone()

        if not table_mats_category:
            # Create the Table Mats category - get next available ID
            result = await db.execute(text("SELECT COALESCE(MAX(id), 0) + 1 FROM categories;"))
            next_id = result.scalar()

            result = await db.execute(
                text(
                    f"""
                INSERT INTO categories (id, name, slug, description, created_at, updated_at)
                VALUES ({next_id}, 'Table Mats', 'table-mats', 'Placemats, table runners, and table linens', NOW(), NOW())
                RETURNING id, name;
            """
                )
            )
            table_mats_category = result.fetchone()
            await db.commit()
            logger.info(f"Created Table Mats category with id={table_mats_category[0]}")

        table_mats_category_id = table_mats_category[0]

        # Update products - placemats, table mats, and runners (excluding floor runners)
        result = await db.execute(
            text(
                f"""
            UPDATE products
            SET category_id = {table_mats_category_id}
            WHERE LOWER(name) LIKE '%placemat%'
               OR LOWER(name) LIKE '%table mat%'
               OR (LOWER(name) LIKE '%runner%' AND LOWER(name) NOT LIKE '%floor runner%');
        """
            )
        )
        await db.commit()
        updated_count = result.rowcount

        # Check final state
        result = await db.execute(
            text(
                """
            SELECT p.category_id, c.name as category_name, COUNT(*) as product_count
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE LOWER(p.name) LIKE '%placemat%'
               OR LOWER(p.name) LIKE '%table mat%'
               OR (LOWER(p.name) LIKE '%runner%' AND LOWER(p.name) NOT LIKE '%floor runner%')
            GROUP BY p.category_id, c.name
            ORDER BY product_count DESC;
        """
            )
        )
        after_state = [{"category_id": row[0], "category_name": row[1], "count": row[2]} for row in result]

        return {
            "success": True,
            "message": f"Migrated {updated_count} products to Table Mats category (id={table_mats_category_id})",
            "before": before_state,
            "after": after_state,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Migration error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Migration failed: {str(e)}")
