"""
Background mask pre-computation service for Edit Position optimization.

This service pre-computes segmentation masks after each visualization completes,
so when users click "Edit Position", the masks are already available for instant retrieval.
"""

import asyncio
import hashlib
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import PrecomputedMask, PrecomputedMaskStatus

logger = logging.getLogger(__name__)


def compute_visualization_hash(visualization_image: str) -> str:
    """
    Create a hash from visualization image for cache key.
    Uses first 1000 chars of base64 + length to balance uniqueness vs performance.
    """
    # Remove data URI prefix if present
    image_data = visualization_image
    if image_data.startswith("data:image"):
        image_data = image_data.split(",")[1] if "," in image_data else image_data

    # Use first 1000 chars + length as hash input (sufficient to detect different images)
    hash_input = f"{image_data[:1000]}:{len(image_data)}"
    return hashlib.sha256(hash_input.encode()).hexdigest()


def compute_product_hash(products: List[Dict[str, Any]]) -> str:
    """
    Create a hash from products list.
    Includes product IDs and names for cache key.
    """
    # Sort for consistent ordering
    product_keys = sorted([f"{p.get('id', p.get('product_id'))}:{p.get('name', '')}" for p in products])
    return hashlib.sha256(":".join(product_keys).encode()).hexdigest()


class MaskPrecomputationService:
    """Service to pre-compute segmentation masks in background."""

    async def trigger_precomputation(
        self,
        db: AsyncSession,
        session_id: str,
        visualization_image: str,
        products: List[Dict[str, Any]],
    ) -> Optional[int]:
        """
        Create a pending precomputation job and return job ID.
        Does NOT wait for completion - returns immediately.
        """
        viz_hash = compute_visualization_hash(visualization_image)
        prod_hash = compute_product_hash(products)

        # Check if we already have a valid cache entry
        existing = await self._find_existing_mask(db, session_id, viz_hash, prod_hash)
        if existing:
            logger.info(f"[Precompute] Cache hit for session {session_id[:8]}... (status: {existing.status.value})")
            return existing.id

        # Create pending job
        mask_record = PrecomputedMask(
            session_id=session_id,
            visualization_hash=viz_hash,
            product_hash=prod_hash,
            status=PrecomputedMaskStatus.PENDING,
        )
        db.add(mask_record)
        await db.commit()
        await db.refresh(mask_record)

        logger.info(f"[Precompute] Created job {mask_record.id} for session {session_id[:8]}...")
        return mask_record.id

    async def process_precomputation(
        self,
        db: AsyncSession,
        job_id: int,
        visualization_image: str,
        products: List[Dict[str, Any]],
    ) -> None:
        """
        Actually run the mask pre-computation.
        Called as a background task.
        """
        from services.google_ai_service import google_ai_service
        from services.sam_service import sam_service
        from core.config import settings

        start_time = datetime.utcnow()

        try:
            # Mark as processing
            await self._update_status(db, job_id, PrecomputedMaskStatus.PROCESSING)

            logger.info(f"[Precompute] Starting job {job_id}")

            # Ensure Replicate API key is set
            replicate_key = settings.replicate_api_key
            if not replicate_key:
                replicate_key = os.environ.get("REPLICATE_API_TOKEN") or os.environ.get("REPLICATE_API_KEY")
            if replicate_key:
                os.environ["REPLICATE_API_TOKEN"] = replicate_key
                sam_service.api_key = replicate_key

            # Step 1: Get product positions from Gemini
            logger.info(f"[Precompute] Job {job_id}: Getting product positions from Gemini...")
            product_positions = await google_ai_service._detect_product_positions(visualization_image, products)
            logger.info(f"[Precompute] Job {job_id}: Gemini detected {len(product_positions)} product positions")

            if len(product_positions) == 0:
                logger.warning(f"[Precompute] Job {job_id}: No product positions detected, skipping")
                await self._mark_failed(db, job_id, "No product positions detected")
                return

            # Step 2: Run SAM segmentation and background removal in parallel
            logger.info(f"[Precompute] Job {job_id}: Running SAM + background removal in parallel...")

            segmentation_task = asyncio.create_task(
                sam_service.segment_all_objects(
                    image_base64=visualization_image,
                    min_area_percent=1.0,
                    max_objects=30,
                    stability_threshold=0.7,
                    furniture_filter=True,
                )
            )

            background_task = asyncio.create_task(google_ai_service.remove_furniture(visualization_image))

            # Wait for both
            segmentation, clean_background = await asyncio.gather(segmentation_task, background_task)

            logger.info(f"[Precompute] Job {job_id}: SAM detected {len(segmentation.objects)} objects")

            # Step 3: Match SAM objects to products (same logic as extract_furniture_layers)
            layers = []
            used_sam_objects = set()

            for pos in product_positions:
                product_bbox = pos.get("bounding_box", pos.get("bbox", {}))
                bbox_x = product_bbox.get("x", 0)
                bbox_y = product_bbox.get("y", 0)
                bbox_w = product_bbox.get("width", 0.2)
                bbox_h = product_bbox.get("height", 0.2)

                product_center_x = bbox_x + bbox_w / 2
                product_center_y = bbox_y + bbox_h / 2

                # Find best matching SAM object
                best_match = None
                best_distance = float("inf")

                for i, obj in enumerate(segmentation.objects):
                    if i in used_sam_objects:
                        continue

                    sam_center_x = obj.center["x"]
                    sam_center_y = obj.center["y"]

                    distance = ((product_center_x - sam_center_x) ** 2 + (product_center_y - sam_center_y) ** 2) ** 0.5

                    sam_bbox = obj.bbox
                    overlap_x = max(
                        0, min(bbox_x + bbox_w, sam_bbox["x"] + sam_bbox["width"]) - max(bbox_x, sam_bbox["x"])
                    )
                    overlap_y = max(
                        0, min(bbox_y + bbox_h, sam_bbox["y"] + sam_bbox["height"]) - max(bbox_y, sam_bbox["y"])
                    )
                    overlap_area = overlap_x * overlap_y

                    if overlap_area > 0 or distance < 0.3:
                        if distance < best_distance:
                            best_distance = distance
                            best_match = (i, obj)

                if best_match:
                    i, obj = best_match
                    used_sam_objects.add(i)

                    sam_center_x = obj.bbox["x"] + obj.bbox["width"] / 2
                    sam_center_y = obj.bbox["y"] + obj.bbox["height"] / 2

                    layers.append(
                        {
                            "id": f"product_{len(layers)}",
                            "product_id": pos.get("product_id"),
                            "product_name": pos.get("product_name", f"Product {len(layers)}"),
                            "cutout": obj.cutout,
                            "mask": obj.mask,
                            "bbox": obj.bbox,
                            "center": obj.center,
                            "x": sam_center_x,
                            "y": sam_center_y,
                            "width": obj.bbox["width"],
                            "height": obj.bbox["height"],
                            "scale": 1.0,
                            "stability_score": obj.stability_score,
                            "area": obj.area,
                        }
                    )

            # If no matches, use SAM objects directly
            sam_match_count = len(used_sam_objects)
            if sam_match_count == 0 and len(segmentation.objects) > 0:
                logger.info(f"[Precompute] Job {job_id}: No SAM matches, using SAM objects directly")
                layers = []
                for i, obj in enumerate(segmentation.objects):
                    if obj.area < 0.01:
                        continue
                    sam_center_x = obj.bbox["x"] + obj.bbox["width"] / 2
                    sam_center_y = obj.bbox["y"] + obj.bbox["height"] / 2
                    layers.append(
                        {
                            "id": f"sam_obj_{i}",
                            "product_id": None,
                            "product_name": f"Object {i+1}",
                            "cutout": obj.cutout,
                            "mask": obj.mask,
                            "bbox": obj.bbox,
                            "center": obj.center,
                            "x": sam_center_x,
                            "y": sam_center_y,
                            "width": obj.bbox["width"],
                            "height": obj.bbox["height"],
                            "scale": 1.0,
                            "stability_score": obj.stability_score,
                            "area": obj.area,
                        }
                    )

            processing_time = (datetime.utcnow() - start_time).total_seconds()

            # Update record with results
            await db.execute(
                update(PrecomputedMask)
                .where(PrecomputedMask.id == job_id)
                .values(
                    status=PrecomputedMaskStatus.COMPLETED,
                    clean_background=clean_background,
                    layers_data=layers,
                    extraction_method="hybrid_gemini_sam" if sam_match_count > 0 else "sam_direct",
                    image_dimensions=segmentation.image_dimensions,
                    processing_time=processing_time,
                    completed_at=datetime.utcnow(),
                )
            )
            await db.commit()

            logger.info(
                f"[Precompute] Job {job_id} completed in {processing_time:.2f}s "
                f"({len(layers)} layers, {sam_match_count} matches)"
            )

        except Exception as e:
            logger.error(f"[Precompute] Job {job_id} failed: {e}", exc_info=True)
            await self._mark_failed(db, job_id, str(e))

    async def get_cached_masks(
        self,
        db: AsyncSession,
        session_id: str,
        visualization_image: str,
        products: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """
        Check if we have valid pre-computed masks.
        Returns None if not found or not ready.
        """
        viz_hash = compute_visualization_hash(visualization_image)
        prod_hash = compute_product_hash(products)

        mask = await self._find_existing_mask(db, session_id, viz_hash, prod_hash)

        if mask and mask.status == PrecomputedMaskStatus.COMPLETED:
            logger.info(f"[Precompute] Cache HIT for session {session_id[:8]}... (job {mask.id})")
            return {
                "background": mask.clean_background,
                "layers": mask.layers_data,
                "extraction_method": f"{mask.extraction_method}_cached",
                "image_dimensions": mask.image_dimensions,
                "processing_time": mask.processing_time,
                "cached": True,
                "cache_job_id": mask.id,
            }

        if mask:
            logger.info(f"[Precompute] Cache exists but status={mask.status.value} for session {session_id[:8]}...")

        return None

    async def invalidate_session_masks(self, db: AsyncSession, session_id: str) -> int:
        """Delete all pre-computed masks for a session."""
        from sqlalchemy import delete

        result = await db.execute(delete(PrecomputedMask).where(PrecomputedMask.session_id == session_id))
        await db.commit()

        deleted_count = result.rowcount
        if deleted_count > 0:
            logger.info(f"[Precompute] Invalidated {deleted_count} masks for session {session_id[:8]}...")
        return deleted_count

    async def _find_existing_mask(
        self,
        db: AsyncSession,
        session_id: str,
        viz_hash: str,
        prod_hash: str,
    ) -> Optional[PrecomputedMask]:
        """Find existing mask record matching the hashes."""
        result = await db.execute(
            select(PrecomputedMask)
            .where(PrecomputedMask.session_id == session_id)
            .where(PrecomputedMask.visualization_hash == viz_hash)
            .where(PrecomputedMask.product_hash == prod_hash)
            .where(
                PrecomputedMask.status.in_(
                    [
                        PrecomputedMaskStatus.PENDING,
                        PrecomputedMaskStatus.PROCESSING,
                        PrecomputedMaskStatus.COMPLETED,
                    ]
                )
            )
        )
        return result.scalar_one_or_none()

    async def _update_status(self, db: AsyncSession, job_id: int, status: PrecomputedMaskStatus) -> None:
        """Update job status."""
        await db.execute(update(PrecomputedMask).where(PrecomputedMask.id == job_id).values(status=status))
        await db.commit()

    async def _mark_failed(self, db: AsyncSession, job_id: int, error_message: str) -> None:
        """Mark job as failed."""
        await db.execute(
            update(PrecomputedMask)
            .where(PrecomputedMask.id == job_id)
            .values(status=PrecomputedMaskStatus.FAILED, error_message=error_message)
        )
        await db.commit()


# Global singleton instance
mask_precomputation_service = MaskPrecomputationService()
