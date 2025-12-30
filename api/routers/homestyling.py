"""
Home Styling API routes for the user-facing home styling flow
"""
import logging
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from schemas.homestyling import (
    CreateSessionRequest,
    HomeStylingSessionSchema,
    HomeStylingViewSchema,
    ProductInView,
    SelectTierRequest,
    TrackEventRequest,
    TrackEventResponse,
    UpdatePreferencesRequest,
    UploadImageRequest,
)
from services.google_ai_service import google_ai_service
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.database import get_db
from database.models import (
    AnalyticsEvent,
    CuratedLook,
    CuratedLookProduct,
    HomeStylingSession,
    HomeStylingSessionStatus,
    HomeStylingTier,
    HomeStylingView,
    Product,
    User,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/homestyling", tags=["homestyling"])


def get_primary_image_url(product: Product) -> Optional[str]:
    """Get the primary image URL for a product"""
    if not product.images:
        return None
    primary = next((img for img in product.images if img.is_primary), None)
    if primary:
        return primary.original_url
    return product.images[0].original_url if product.images else None


# =============================================================================
# SESSION MANAGEMENT
# =============================================================================


@router.post("/sessions", response_model=HomeStylingSessionSchema)
async def create_session(
    request: CreateSessionRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new home styling session.

    This is the first step in the home styling flow. The session tracks
    user preferences, uploaded images, and generated views.
    """
    try:
        session = HomeStylingSession(
            id=str(uuid.uuid4()),
            room_type=request.room_type.value if request.room_type else None,
            style=request.style.value if request.style else None,
            color_palette=[c.value for c in request.color_palette] if request.color_palette else [],
            status=HomeStylingSessionStatus.PREFERENCES,
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)

        logger.info(f"Created home styling session: {session.id}")

        return HomeStylingSessionSchema(
            id=session.id,
            user_id=session.user_id,
            room_type=session.room_type,
            style=session.style,
            color_palette=session.color_palette or [],
            original_room_image=None,  # Don't return large images in list responses
            clean_room_image=None,
            selected_tier=session.selected_tier.value if session.selected_tier else None,
            views_count=session.views_count,
            status=session.status.value,
            views=[],
            created_at=session.created_at,
            updated_at=session.updated_at,
        )
    except Exception as e:
        logger.error(f"Error creating session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create session: {str(e)}")


@router.get("/sessions/{session_id}", response_model=HomeStylingSessionSchema)
async def get_session(
    session_id: str,
    include_images: bool = Query(False, description="Include base64 images in response"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get a home styling session by ID.
    """
    try:
        query = (
            select(HomeStylingSession)
            .where(HomeStylingSession.id == session_id)
            .options(
                selectinload(HomeStylingSession.views)
                .selectinload(HomeStylingView.curated_look)
                .selectinload(CuratedLook.products)
                .selectinload(CuratedLookProduct.product)
                .selectinload(Product.images)
            )
        )
        result = await db.execute(query)
        session = result.scalars().first()

        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Build views list with products
        views = []
        for view in sorted(session.views, key=lambda v: v.view_number):
            products = []
            total_price = 0
            style_theme = None

            if view.curated_look:
                style_theme = view.curated_look.style_theme
                for lp in view.curated_look.products:
                    if lp.product:
                        product_price = lp.product.price or 0
                        total_price += product_price
                        products.append(
                            ProductInView(
                                id=lp.product.id,
                                name=lp.product.name,
                                price=product_price,
                                image_url=get_primary_image_url(lp.product),
                                source_website=lp.product.source_website,
                                source_url=lp.product.source_url,
                                product_type=lp.product_type,
                            )
                        )

            views.append(
                HomeStylingViewSchema(
                    id=view.id,
                    view_number=view.view_number,
                    visualization_image=view.visualization_image if include_images else None,
                    curated_look_id=view.curated_look_id,
                    style_theme=style_theme,
                    generation_status=view.generation_status,
                    error_message=view.error_message,
                    products=products,
                    total_price=total_price,
                )
            )

        return HomeStylingSessionSchema(
            id=session.id,
            user_id=session.user_id,
            room_type=session.room_type,
            style=session.style,
            color_palette=session.color_palette or [],
            original_room_image=session.original_room_image if include_images else None,
            clean_room_image=session.clean_room_image if include_images else None,
            selected_tier=session.selected_tier.value if session.selected_tier else None,
            views_count=session.views_count,
            status=session.status.value,
            views=views,
            created_at=session.created_at,
            updated_at=session.updated_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session {session_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get session: {str(e)}")


@router.patch("/sessions/{session_id}", response_model=HomeStylingSessionSchema)
async def update_preferences(
    session_id: str,
    request: UpdatePreferencesRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Update session preferences (room type, style, color palette).
    """
    try:
        query = select(HomeStylingSession).where(HomeStylingSession.id == session_id)
        result = await db.execute(query)
        session = result.scalars().first()

        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        if request.room_type is not None:
            session.room_type = request.room_type.value
        if request.style is not None:
            session.style = request.style.value
        if request.color_palette is not None:
            session.color_palette = [c.value for c in request.color_palette]

        await db.commit()
        await db.refresh(session)

        logger.info(f"Updated preferences for session: {session_id}")

        return HomeStylingSessionSchema(
            id=session.id,
            user_id=session.user_id,
            room_type=session.room_type,
            style=session.style,
            color_palette=session.color_palette or [],
            original_room_image=None,
            clean_room_image=None,
            selected_tier=session.selected_tier.value if session.selected_tier else None,
            views_count=session.views_count,
            status=session.status.value,
            views=[],
            created_at=session.created_at,
            updated_at=session.updated_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating session {session_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update session: {str(e)}")


# =============================================================================
# IMAGE UPLOAD
# =============================================================================


@router.post("/sessions/{session_id}/upload")
async def upload_room_image(
    session_id: str,
    request: UploadImageRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a room image for the session.

    This endpoint:
    1. Saves the original image
    2. Processes it to remove existing furniture (TODO: implement furniture removal)
    3. Updates the session status to 'upload'
    """
    try:
        query = select(HomeStylingSession).where(HomeStylingSession.id == session_id)
        result = await db.execute(query)
        session = result.scalars().first()

        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Handle base64 prefix if present
        image_data = request.image
        if image_data.startswith("data:image"):
            image_data = image_data.split(",", 1)[1] if "," in image_data else image_data

        # Store original image
        session.original_room_image = image_data

        # Remove furniture from the image using Google AI
        logger.info(f"Starting furniture removal for session: {session_id}")
        try:
            clean_image = await google_ai_service.remove_furniture(image_data, max_retries=3)
            if clean_image:
                session.clean_room_image = clean_image
                logger.info(f"Furniture removal successful for session: {session_id}")
            else:
                # Fallback to original if removal fails
                logger.warning(f"Furniture removal returned None for session: {session_id}, using original")
                session.clean_room_image = image_data
        except Exception as removal_error:
            # Fallback to original if removal fails
            logger.warning(f"Furniture removal failed for session {session_id}: {removal_error}, using original")
            session.clean_room_image = image_data

        # Update status
        session.status = HomeStylingSessionStatus.UPLOAD

        await db.commit()

        logger.info(f"Uploaded room image for session: {session_id}")

        return {
            "success": True,
            "message": "Image uploaded and processed successfully",
            "session_id": session_id,
            "status": session.status.value,
            "clean_room_image": session.clean_room_image,  # Return the processed image
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading image for session {session_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to upload image: {str(e)}")


# =============================================================================
# TIER SELECTION
# =============================================================================


@router.post("/sessions/{session_id}/select-tier")
async def select_tier(
    session_id: str,
    request: SelectTierRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Select a tier for the session.

    Tiers:
    - free: 1 view
    - basic: 3 views
    - premium: 6 views (coming soon)
    """
    try:
        query = select(HomeStylingSession).where(HomeStylingSession.id == session_id)
        result = await db.execute(query)
        session = result.scalars().first()

        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Premium is coming soon
        if request.tier.value == "premium":
            raise HTTPException(status_code=400, detail="Premium tier is coming soon")

        # Set tier and views count
        tier_views = {
            "free": 1,
            "basic": 3,
            "premium": 6,
        }

        session.selected_tier = HomeStylingTier(request.tier.value)
        session.views_count = tier_views[request.tier.value]
        session.status = HomeStylingSessionStatus.TIER_SELECTION

        await db.commit()

        logger.info(f"Selected tier {request.tier.value} for session: {session_id}")

        return {
            "success": True,
            "message": f"Selected {request.tier.value} tier ({session.views_count} views)",
            "session_id": session_id,
            "tier": request.tier.value,
            "views_count": session.views_count,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error selecting tier for session {session_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to select tier: {str(e)}")


# =============================================================================
# VIEW GENERATION
# =============================================================================


@router.post("/sessions/{session_id}/generate")
async def generate_views(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Generate visualizations for the session.

    This endpoint:
    1. Finds matching curated looks based on style and room type
    2. For each look, generates a new visualization using the user's room image + products
    3. Stores the generated visualizations
    """
    try:
        # Get session with views
        query = (
            select(HomeStylingSession)
            .where(HomeStylingSession.id == session_id)
            .options(selectinload(HomeStylingSession.views))
        )
        result = await db.execute(query)
        session = result.scalars().first()

        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Validate session has required data
        if not session.room_type:
            raise HTTPException(status_code=400, detail="Room type not selected")
        if not session.style:
            raise HTTPException(status_code=400, detail="Style not selected")
        if not session.clean_room_image:
            raise HTTPException(status_code=400, detail="Room image not uploaded")
        if not session.selected_tier:
            raise HTTPException(status_code=400, detail="Tier not selected")

        # Update status to generating
        session.status = HomeStylingSessionStatus.GENERATING
        await db.commit()

        # Find matching curated looks WITH their products
        # STRICT style matching - only get looks that have the user's selected style
        logger.info(f"Finding curated looks for room_type='{session.room_type}', style='{session.style}'")

        looks_query = (
            select(CuratedLook)
            .where(CuratedLook.is_published.is_(True))
            .where(CuratedLook.room_type == session.room_type)
            .where(CuratedLook.style_labels.cast(JSONB).contains([session.style]))
            .options(selectinload(CuratedLook.products).selectinload(CuratedLookProduct.product).selectinload(Product.images))
            .order_by(func.random())
            .limit(session.views_count)
        )

        looks_result = await db.execute(looks_query)
        looks = looks_result.scalars().all()

        logger.info(f"Found {len(looks)} curated looks matching style '{session.style}'")

        if not looks:
            session.status = HomeStylingSessionStatus.FAILED
            await db.commit()
            raise HTTPException(
                status_code=404, detail=f"No curated looks found for {session.room_type} with {session.style} style"
            )

        # Get the user's clean room image (furniture removed)
        user_room_image = session.clean_room_image
        # Remove data URL prefix if present
        if user_room_image.startswith("data:"):
            user_room_image = user_room_image.split(",", 1)[1] if "," in user_room_image else user_room_image

        logger.info(f"Generating {len(looks)} views for session {session_id}")

        # Generate visualization for each look
        for i, look in enumerate(looks):
            view_number = i + 1
            logger.info(f"Generating view {view_number}/{len(looks)} using look '{look.title}' (ID: {look.id})")

            # Build products list for visualization
            products_for_viz = []
            for lp in look.products:
                if lp.product:
                    # Get primary image URL
                    image_url = None
                    if lp.product.images:
                        primary = next((img for img in lp.product.images if img.is_primary), None)
                        if primary:
                            image_url = primary.original_url
                        elif lp.product.images:
                            image_url = lp.product.images[0].original_url

                    products_for_viz.append(
                        {
                            "name": lp.product.name,
                            "full_name": lp.product.name,
                            "image_url": image_url,
                            "quantity": lp.quantity or 1,
                        }
                    )

            # Create view placeholder with pending status
            view = HomeStylingView(
                session_id=session_id,
                curated_look_id=look.id,
                visualization_image=None,
                view_number=view_number,
                generation_status="generating",
            )
            db.add(view)
            await db.flush()  # Get the view ID

            try:
                # Generate visualization using user's room + products
                if products_for_viz:
                    logger.info(f"  Calling AI visualizer with {len(products_for_viz)} products")
                    visualization_image = await google_ai_service.generate_add_multiple_visualization(
                        room_image=user_room_image, products=products_for_viz
                    )
                    view.visualization_image = visualization_image
                    view.generation_status = "completed"
                    logger.info(f"  View {view_number} generated successfully")
                else:
                    # No products, use the original room image
                    view.visualization_image = user_room_image
                    view.generation_status = "completed"
                    logger.warning(f"  No products found for look {look.id}, using room image")

            except Exception as viz_error:
                logger.error(f"  Failed to generate view {view_number}: {viz_error}")
                view.generation_status = "failed"
                view.error_message = str(viz_error)
                # Use the curated look's visualization as fallback
                view.visualization_image = look.visualization_image

            await db.commit()

        # Update session status
        session.status = HomeStylingSessionStatus.COMPLETED
        await db.commit()

        logger.info(f"Completed generating {len(looks)} views for session: {session_id}")

        return {
            "success": True,
            "message": f"Generated {len(looks)} views",
            "session_id": session_id,
            "views_count": len(looks),
            "status": session.status.value,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating views for session {session_id}: {e}", exc_info=True)
        # Update status to failed
        try:
            session.status = HomeStylingSessionStatus.FAILED
            await db.commit()
        except:
            pass
        raise HTTPException(status_code=500, detail=f"Failed to generate views: {str(e)}")


@router.get("/sessions/{session_id}/views", response_model=List[HomeStylingViewSchema])
async def get_session_views(
    session_id: str,
    include_images: bool = Query(True, description="Include visualization images"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get all generated views for a session.
    """
    try:
        query = (
            select(HomeStylingView)
            .where(HomeStylingView.session_id == session_id)
            .options(
                selectinload(HomeStylingView.curated_look)
                .selectinload(CuratedLook.products)
                .selectinload(CuratedLookProduct.product)
                .selectinload(Product.images)
            )
            .order_by(HomeStylingView.view_number)
        )

        result = await db.execute(query)
        views = result.scalars().all()

        response = []
        for view in views:
            products = []
            total_price = 0
            style_theme = None

            if view.curated_look:
                style_theme = view.curated_look.style_theme
                for lp in view.curated_look.products:
                    if lp.product:
                        product_price = lp.product.price or 0
                        total_price += product_price
                        products.append(
                            ProductInView(
                                id=lp.product.id,
                                name=lp.product.name,
                                price=product_price,
                                image_url=get_primary_image_url(lp.product),
                                source_website=lp.product.source_website,
                                source_url=lp.product.source_url,
                                product_type=lp.product_type,
                            )
                        )

            response.append(
                HomeStylingViewSchema(
                    id=view.id,
                    view_number=view.view_number,
                    visualization_image=view.visualization_image if include_images else None,
                    curated_look_id=view.curated_look_id,
                    style_theme=style_theme,
                    generation_status=view.generation_status,
                    error_message=view.error_message,
                    products=products,
                    total_price=total_price,
                )
            )

        return response
    except Exception as e:
        logger.error(f"Error getting views for session {session_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get views: {str(e)}")


# =============================================================================
# ANALYTICS
# =============================================================================


@router.post("/analytics/track", response_model=TrackEventResponse)
async def track_event(
    request: TrackEventRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Track an analytics event.
    """
    try:
        event = AnalyticsEvent(
            event_type=request.event_type,
            session_id=request.session_id,
            step_name=request.step_name,
            event_data=request.event_data or {},
        )
        db.add(event)
        await db.commit()
        await db.refresh(event)

        return TrackEventResponse(success=True, event_id=event.id)
    except Exception as e:
        logger.error(f"Error tracking event: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to track event: {str(e)}")
