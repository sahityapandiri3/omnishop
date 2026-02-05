"""
Projects API routes for saving and managing user design work
"""
import base64
import io
import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from PIL import Image
from pydantic import BaseModel
from schemas.projects import ProjectCreate, ProjectListItem, ProjectResponse, ProjectsListResponse, ProjectUpdate
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import get_current_user, get_optional_user
from core.database import get_db
from database.models import HomeStylingSession, HomeStylingSessionStatus, Project, ProjectStatus, User


# Schema for previous room images
class PreviousRoomImage(BaseModel):
    """A previously uploaded room image that can be reused."""

    id: str  # Project ID or session ID
    source: str  # "project" or "homestyling"
    name: Optional[str] = None  # Project name if from project
    thumbnail: str  # Base64 encoded thumbnail
    created_at: datetime


class PreviousRoomImagesResponse(BaseModel):
    """Response containing list of previous room images."""

    rooms: List[PreviousRoomImage]
    total: int


logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("", response_model=ProjectsListResponse)
async def list_projects(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all projects for the current user.
    Returns projects without large image data for fast loading.
    """
    # Get projects ordered by most recently updated
    query = select(Project).where(Project.user_id == current_user.id).order_by(Project.updated_at.desc())
    result = await db.execute(query)
    projects = result.scalars().all()

    # Get total count
    count_query = select(func.count()).select_from(Project).where(Project.user_id == current_user.id)
    count_result = await db.execute(count_query)
    total = count_result.scalar()

    # Convert to list items (without large image data)
    project_items = [
        ProjectListItem(
            id=p.id,
            name=p.name,
            status=p.status.value if p.status else "draft",  # Convert enum to string
            has_room_image=bool(p.room_image),
            has_visualization=bool(p.visualization_image),
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p in projects
    ]

    return ProjectsListResponse(projects=project_items, total=total)


def _project_to_response(project: Project) -> ProjectResponse:
    """Convert a Project ORM object to a ProjectResponse, handling enum conversion."""
    return ProjectResponse(
        id=project.id,
        name=project.name,
        status=project.status.value if project.status else "draft",
        room_image=project.room_image,
        clean_room_image=project.clean_room_image,
        visualization_image=project.visualization_image,
        canvas_products=project.canvas_products,
        visualization_history=project.visualization_history,
        chat_session_id=project.chat_session_id,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_data: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new project for the current user.
    """
    project = Project(
        user_id=current_user.id,
        name=project_data.name,
    )

    db.add(project)
    await db.commit()
    await db.refresh(project)

    logger.info(f"Created project {project.id} for user {current_user.id}")

    return _project_to_response(project)


@router.get("/previous-rooms", response_model=PreviousRoomImagesResponse)
async def get_previous_room_images(
    exclude_project_id: Optional[str] = Query(None, description="Project ID to exclude from results"),
    limit: int = Query(10, ge=1, le=50, description="Maximum number of rooms to return"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get previously uploaded room images that can be reused in new projects.

    Returns clean room images (furniture removed) from:
    - Design projects
    - Home styling sessions

    Images are returned as thumbnails for efficient loading.
    """
    rooms: List[PreviousRoomImage] = []

    try:
        # Fetch from design projects with clean_room_image
        project_query = (
            select(Project)
            .where(
                Project.user_id == current_user.id,
                Project.clean_room_image.isnot(None),
            )
            .order_by(Project.updated_at.desc())
            .limit(limit)
        )

        # Exclude current project if specified
        if exclude_project_id:
            project_query = project_query.where(Project.id != exclude_project_id)

        result = await db.execute(project_query)
        projects = result.scalars().all()

        for project in projects:
            if project.clean_room_image:
                thumbnail = _create_thumbnail(project.clean_room_image)
                rooms.append(
                    PreviousRoomImage(
                        id=project.id,
                        source="project",
                        name=project.name,
                        thumbnail=thumbnail,
                        created_at=project.updated_at or project.created_at,
                    )
                )

        # Also fetch from home styling sessions
        homestyling_query = (
            select(HomeStylingSession)
            .where(
                HomeStylingSession.user_id == current_user.id,
                HomeStylingSession.clean_room_image.isnot(None),
                HomeStylingSession.source_session_id.is_(None),  # Only originals, not copies
            )
            .order_by(HomeStylingSession.created_at.desc())
            .limit(limit)
        )

        result = await db.execute(homestyling_query)
        sessions = result.scalars().all()

        for session in sessions:
            if session.clean_room_image:
                thumbnail = _create_thumbnail(session.clean_room_image)
                rooms.append(
                    PreviousRoomImage(
                        id=session.id,
                        source="homestyling",
                        name=f"{session.room_type or 'Room'} - {session.style or 'Custom'}",
                        thumbnail=thumbnail,
                        created_at=session.created_at,
                    )
                )

        # Deduplicate: if the same clean_room_image exists in both projects and
        # homestyling_sessions, keep only the project entry (it has a better name).
        # We compare thumbnails since they're derived from the same clean_room_image.
        seen_thumbnails = set()
        deduped_rooms: List[PreviousRoomImage] = []
        # Process project-sourced rooms first so they win over homestyling duplicates
        rooms.sort(key=lambda r: (0 if r.source == "project" else 1, r.created_at), reverse=False)
        for room in rooms:
            thumb_key = room.thumbnail[:200]  # First 200 chars of thumbnail is enough to identify
            if thumb_key not in seen_thumbnails:
                seen_thumbnails.add(thumb_key)
                deduped_rooms.append(room)

        # Sort by date and limit total
        deduped_rooms.sort(key=lambda r: r.created_at, reverse=True)
        deduped_rooms = deduped_rooms[:limit]

        return PreviousRoomImagesResponse(rooms=deduped_rooms, total=len(deduped_rooms))

    except Exception as e:
        logger.error(f"Error getting previous room images: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get previous room images: {str(e)}")


@router.get("/previous-rooms/{room_id}/image")
async def get_previous_room_full_image(
    room_id: str,
    source: str = Query(..., description="Source of the room: 'project' or 'homestyling'"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the full clean room image for a previously uploaded room.
    Used by onboarding flow where no project exists yet.
    """
    clean_room_image = None

    if source == "project":
        query = select(Project).where(
            Project.id == room_id,
            Project.user_id == current_user.id,
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()
        if project:
            clean_room_image = project.clean_room_image

    elif source == "homestyling":
        query = select(HomeStylingSession).where(
            HomeStylingSession.id == room_id,
            HomeStylingSession.user_id == current_user.id,
        )
        result = await db.execute(query)
        session = result.scalar_one_or_none()
        if session:
            clean_room_image = session.clean_room_image

    if not clean_room_image:
        raise HTTPException(status_code=404, detail="Previous room not found")

    return {"clean_room_image": clean_room_image}


class SaveRoomImageRequest(BaseModel):
    """Save a clean room image immediately after furniture removal."""

    original_room_image: str  # base64 original image
    clean_room_image: str  # base64 furniture-removed image
    room_analysis: Optional[dict] = None  # Room analysis JSON from Gemini


@router.post("/save-room-image")
async def save_room_image(
    request: SaveRoomImageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Save a clean room image to DB immediately after furniture removal.
    Creates a minimal HomeStylingSession record so the image appears
    in "Previously Uploaded" rooms.

    This is called fire-and-forget by the frontend -- it doesn't block the UI.
    """
    # Check if this clean image is already saved (avoid duplicates)
    existing_query = (
        select(HomeStylingSession)
        .where(
            HomeStylingSession.user_id == current_user.id,
            HomeStylingSession.clean_room_image.isnot(None),
        )
        .order_by(HomeStylingSession.created_at.desc())
        .limit(5)
    )
    result = await db.execute(existing_query)
    existing_sessions = result.scalars().all()

    for session in existing_sessions:
        if session.clean_room_image == request.clean_room_image:
            return {"status": "already_saved", "session_id": session.id}

    # Extract room type from room_analysis if available
    room_type = None
    style = None
    if request.room_analysis:
        room_type = request.room_analysis.get("room_type")
        style = request.room_analysis.get("style_assessment")

    # Create minimal HomeStylingSession
    session = HomeStylingSession(
        user_id=current_user.id,
        original_room_image=request.original_room_image,
        clean_room_image=request.clean_room_image,
        room_type=room_type,
        style=style,
        status=HomeStylingSessionStatus.UPLOAD,
    )
    db.add(session)
    await db.commit()

    logger.info(f"Saved room image for user {current_user.id}, session {session.id}")
    return {"status": "saved", "session_id": session.id}


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get a specific project by ID.
    Returns full project data including images.
    """
    query = select(Project).where(
        Project.id == project_id,
        Project.user_id == current_user.id,
    )
    result = await db.execute(query)
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    return _project_to_response(project)


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    project_data: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update a project (used for auto-save).
    Only updates fields that are provided.
    """
    query = select(Project).where(
        Project.id == project_id,
        Project.user_id == current_user.id,
    )
    result = await db.execute(query)
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # Update only provided fields
    update_data = project_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        # Handle status enum conversion
        if field == "status" and value is not None:
            value = ProjectStatus(value.upper()) if isinstance(value, str) else value
        setattr(project, field, value)

    # Always update the timestamp
    project.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(project)

    logger.debug(f"Updated project {project_id} (fields: {list(update_data.keys())})")

    return _project_to_response(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a project.
    """
    query = select(Project).where(
        Project.id == project_id,
        Project.user_id == current_user.id,
    )
    result = await db.execute(query)
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    await db.delete(project)
    await db.commit()

    logger.info(f"Deleted project {project_id} for user {current_user.id}")

    return None


@router.get("/{project_id}/thumbnail")
async def get_project_thumbnail(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the visualization thumbnail for a project.
    Returns only the visualization image for efficient loading in project list.
    """
    query = select(Project.visualization_image).where(
        Project.id == project_id,
        Project.user_id == current_user.id,
    )
    result = await db.execute(query)
    visualization_image = result.scalar_one_or_none()

    if visualization_image is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found or no visualization",
        )

    return {"visualization_image": visualization_image}


def _create_thumbnail(image_base64: str, max_width: int = 300) -> str:
    """Create a thumbnail from a base64 image for efficient loading."""
    try:
        # Skip if already a data URI
        if image_base64.startswith("data:"):
            # Extract base64 part
            image_base64 = image_base64.split(",", 1)[1] if "," in image_base64 else image_base64

        img_data = base64.b64decode(image_base64)
        img = Image.open(io.BytesIO(img_data))

        # Resize if larger than max_width
        if img.width > max_width:
            ratio = max_width / img.width
            new_size = (max_width, int(img.height * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)

        # Convert to JPEG for smaller size
        buffer = io.BytesIO()
        img.convert("RGB").save(buffer, format="JPEG", quality=70)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")
    except Exception as e:
        logger.warning(f"Failed to create thumbnail: {e}")
        # Return original if thumbnail creation fails
        return image_base64


@router.post("/{project_id}/use-previous-room")
async def use_previous_room(
    project_id: str,
    previous_room_id: str = Query(..., description="ID of the previous room to use"),
    source: str = Query(..., description="Source of the room: 'project' or 'homestyling'"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Copy a previously uploaded room image to the current project.
    """
    # Get current project
    project_query = select(Project).where(
        Project.id == project_id,
        Project.user_id == current_user.id,
    )
    result = await db.execute(project_query)
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Get the source room image
    clean_room_image = None
    room_image = None

    if source == "project":
        source_query = select(Project).where(
            Project.id == previous_room_id,
            Project.user_id == current_user.id,
        )
        result = await db.execute(source_query)
        source_project = result.scalar_one_or_none()

        if not source_project or not source_project.clean_room_image:
            raise HTTPException(status_code=404, detail="Previous room not found")

        clean_room_image = source_project.clean_room_image
        room_image = source_project.room_image

    elif source == "homestyling":
        source_query = select(HomeStylingSession).where(
            HomeStylingSession.id == previous_room_id,
            HomeStylingSession.user_id == current_user.id,
        )
        result = await db.execute(source_query)
        source_session = result.scalar_one_or_none()

        if not source_session or not source_session.clean_room_image:
            raise HTTPException(status_code=404, detail="Previous room not found")

        clean_room_image = source_session.clean_room_image
        room_image = source_session.original_room_image

    else:
        raise HTTPException(status_code=400, detail="Invalid source type")

    # Update the current project with the room images
    project.room_image = room_image
    project.clean_room_image = clean_room_image
    project.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(project)

    logger.info(f"Copied room image from {source}/{previous_room_id} to project {project_id}")

    return {
        "success": True,
        "room_image": room_image,
        "clean_room_image": clean_room_image,
    }
